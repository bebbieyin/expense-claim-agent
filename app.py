"""Streamlit interface for the expense claim review app."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import streamlit as st
from sqlalchemy import func, select

from src.client.langfuse_client import get_trace_url
from src.database.entities import Claim, Employee
from src.database.operations import (
    SessionLocal,
    create_claim,
    get_claim,
    list_claims,
    list_claims_needing_review,
    list_employees,
    resolve_claim_review,
    run_migrations,
    update_claim_review,
    update_receipt_correction,
)
from src.shared.schemas import ClaimCreate, ExtractedReceipt
from src.shared.utils import next_claim_id, save_uploaded_receipt
from src.workflow.agents import run_review
from src.workflow.policy import POLICIES
from src.workflow.validation import validate_claim

EXPENSE_CATEGORIES = ["Meals", "Transport", "Office Supplies", "Medical"]
DEPARTMENTS = ["Sales & Marketing", "IT", "HR", "Finance", "Operations"]


@st.cache_resource(show_spinner=False)
def initialize_database() -> None:
    """Apply database migrations once per Streamlit process."""
    run_migrations()


def _render_checks(title: str, checks: list[dict[str, str]]) -> None:
    st.subheader(title)
    if not checks:
        st.info("No results recorded.")
        return
    for check in checks:
        icon = {"passed": "✅", "failed": "❌", "warning": "⚠️"}.get(
            check["status"],
            "-",
        )
        label = check["check"].replace("_", " ").title()
        st.write(f"{icon} **{label}** — {check['message']}")


def _optional_receipt_date(value: str) -> str | None:
    """Validate and normalize an optional corrected receipt date."""
    normalized = value.strip()
    if not normalized:
        return None
    return date.fromisoformat(normalized).isoformat()


def _optional_amount(value: str) -> float | None:
    """Validate an optional corrected receipt amount."""
    normalized = value.strip()
    if not normalized:
        return None
    amount = float(normalized)
    if amount < 0:
        msg = "Receipt total cannot be negative."
        raise ValueError(msg)
    return amount


def render_submit_tab(employee: Employee) -> None:
    """Render and process the expense submission form."""
    st.header("Submit Expense Claim")
    st.text_input("Employee ID", value=employee.employee_id, disabled=True)

    receipt = st.file_uploader(
        "Receipt image",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=False,
    )
    if receipt is not None:
        st.image(receipt, caption=receipt.name, width=500)

    with st.form("claim-form", clear_on_submit=False):
        left, right = st.columns(2)
        department = left.selectbox("Department", DEPARTMENTS)
        claim_date = right.date_input("Claim date", value=datetime.now(tz=UTC).date())
        category = left.selectbox("Expense category", EXPENSE_CATEGORIES)
        claimed_amount = right.number_input(
            "Claimed amount (MYR)",
            min_value=0.01,
            value=45.90,
            step=0.01,
        )
        purpose = st.text_area("Expense purpose")
        submitted = st.form_submit_button("Submit", type="primary")

    if not submitted:
        return
    required_fields = [department, purpose]
    if not all(value.strip() for value in required_fields):
        st.error("Complete all text fields before submitting.")
        return
    if receipt is None:
        st.error("Upload a receipt image before submitting.")
        return

    with st.spinner("Submitting and reviewing your claim...", show_time=True):
        receipt_path = save_uploaded_receipt(receipt, receipt.name)
        with SessionLocal() as session:
            last_id = session.scalar(select(func.max(Claim.id)))
            claim_data = ClaimCreate(
                claim_id=next_claim_id(last_id),
                employee_id=employee.employee_id,
                employee_name=employee.employee_name,
                department=department.strip(),
                claim_date=claim_date,
                expense_category=category,
                expense_purpose=purpose.strip(),
                claimed_amount=claimed_amount,
                currency="MYR",
                receipt_file_path=receipt_path,
            )
            claim = create_claim(session, claim_data)
            try:
                state = run_review(
                    claim_data.model_dump(mode="json"),
                    receipt_path,
                    session,
                    claim.id,
                )
                update_claim_review(session, claim, state)
            except Exception as exc:  # noqa: BLE001
                claim.status = "failed"
                claim.review_summary = f"Review failed: {exc}"
                claim.langfuse_trace_id = getattr(exc, "langfuse_trace_id", None)
                session.commit()
                st.error(f"Claim {claim.claim_id} was stored, but review failed.")
                return

    if state["decision"] == "needs_review":
        st.warning(
            f"{claim.claim_id} needs review and has been escalated to the "
            "reviewer team.",
        )
    else:
        st.success(f"{claim.claim_id}: {state['decision']}")
    st.write(state["review_summary"])


def render_dashboard_tab(employee_id: str | None = None) -> None:
    """Render claims available to the current view."""
    st.header("My Claims" if employee_id else "Finance Claims Dashboard")
    with SessionLocal() as session:
        claims = list_claims(session, employee_id)
    if not claims:
        st.info("No claims have been submitted.")
        return
    rows = [
        {
            "Claim ID": claim.claim_id,
            "Employee": claim.employee_name,
            "Department": claim.department,
            "Category": claim.expense_category,
            "Claimed Amount": claim.claimed_amount,
            "Currency": claim.currency,
            "Decision": claim.decision or "—",
            "Status": claim.status,
            "Created At": claim.created_at,
        }
        for claim in claims
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_approval_queue_tab() -> None:
    """Render claims escalated for an approver decision."""
    st.header("Claims Requiring Approval")
    with SessionLocal() as session:
        claims = list_claims_needing_review(session)
    if not claims:
        st.info("No claims are waiting for human review.")
        return

    claim_ids = [claim.claim_id for claim in claims]
    selected_id = st.selectbox(
        "Claim ID",
        claim_ids,
        key="approval-queue-claim",
    )
    with SessionLocal() as session:
        claim = get_claim(session, selected_id)
    if claim is None:
        st.error("Claim could not be found.")
        return

    _render_original_claim(claim)
    state = json.loads(claim.raw_agent_state or "{}")
    _render_checks("Validation Results", state.get("validation_results", []))
    _render_checks("Policy Results", state.get("policy_results", []))
    _render_checks("Duplicate Check", state.get("duplicate_results", []))
    st.subheader("Escalation Reason")
    st.write(claim.review_summary or "No review summary recorded.")

    with st.form(f"human-review-{claim.claim_id}"):
        decision = st.radio(
            "Decision",
            ["approved", "rejected"],
            horizontal=True,
        )
        notes = st.text_area("Review notes")
        submitted = st.form_submit_button("Submit Decision", type="primary")

    if not submitted:
        return
    with SessionLocal() as session:
        review_claim = get_claim(session, claim.claim_id)
        if review_claim is None:
            st.error("Claim could not be found.")
            return
        try:
            resolve_claim_review(
                session,
                review_claim,
                decision,
                notes.strip(),
                "Reviewer Team",
            )
        except ValueError as exc:
            st.error(str(exc))
            return
    st.success(f"{claim.claim_id} was {decision}.")
    st.rerun()


def render_review_rules_tab() -> None:
    """Render the expense policy and validation checks."""
    st.header("Expense Policy and Validation Checks")
    st.subheader("Expense Policy")
    st.write(
        "Claims are reviewed against the category limits and receipt "
        "requirements below.",
    )
    rows = [
        {
            "Expense Category": category,
            "Maximum Amount": float(policy["max_amount"]),
            "Currency": "MYR",
            "Receipt Required": "Yes" if policy["receipt_required"] else "No",
        }
        for category, policy in POLICIES.items()
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.info(
        "Claims above the maximum amount are rejected. Missing receipts and "
        "receipt details that do not match the claim require manual review.",
    )

    st.subheader("Validation Checks")
    st.write("The submitted claim is compared with the extracted receipt details.")
    validation_rows = [
        {
            "Check": "Amount match",
            "Requirement": "Claimed amount must match the receipt total.",
        },
        {
            "Check": "Receipt date",
            "Requirement": "Receipt date must be on or before the claim date.",
        },
        {
            "Check": "Merchant name",
            "Requirement": "The receipt must contain a merchant name.",
        },
        {
            "Check": "Receipt total",
            "Requirement": "The receipt must contain a total amount.",
        },
        {
            "Check": "Currency match",
            "Requirement": "Claim and receipt currencies must match.",
        },
        {
            "Check": "Positive amount",
            "Requirement": "The claimed amount must be greater than zero.",
        },
        {
            "Check": "Duplicate receipt",
            "Requirement": "The receipt must not match an earlier employee claim.",
        },
        {
            "Check": "Extraction confidence",
            "Requirement": "Receipt extraction confidence must be at least 75%.",
        },
    ]
    st.dataframe(validation_rows, use_container_width=True, hide_index=True)


def render_receipt_correction(
    claim: Claim,
    extracted_receipt: dict[str, object],
    employee_id: str | None,
) -> None:
    """Render and process human verification of extracted receipt fields."""
    corrected_receipt = claim.corrected_receipt
    correction_values = corrected_receipt or extracted_receipt

    st.subheader("Verify Receipt Extraction")
    st.write(
        "Confirm or correct the extracted fields. The original AI extraction "
        "will remain unchanged for evaluation.",
    )
    with st.form(f"receipt-correction-{claim.claim_id}"):
        merchant_name = st.text_input(
            "Merchant name",
            value=str(correction_values.get("merchant_name") or ""),
        )
        merchant_address = st.text_area(
            "Merchant address",
            value=str(correction_values.get("merchant_address") or ""),
        )
        receipt_date = st.text_input(
            "Receipt date (YYYY-MM-DD)",
            value=str(correction_values.get("receipt_date") or ""),
        )
        total_amount = st.text_input(
            "Receipt total",
            value=(
                str(correction_values["total_amount"])
                if correction_values.get("total_amount") is not None
                else ""
            ),
        )
        currency = st.text_input(
            "Currency",
            value=str(correction_values.get("currency") or ""),
        )
        correction_submitted = st.form_submit_button(
            "Save & Re-run Validation",
            type="primary",
        )

    if correction_submitted:
        try:
            corrected_receipt = {
                "merchant_name": merchant_name.strip() or None,
                "merchant_address": merchant_address.strip() or None,
                "receipt_date": _optional_receipt_date(receipt_date),
                "total_amount": _optional_amount(total_amount),
                "currency": currency.strip().upper() or None,
            }
        except ValueError:
            st.error(
                "Use YYYY-MM-DD for the receipt date and a valid non-negative "
                "number for the receipt total.",
            )
            return

        corrected_by = employee_id or "Finance Team"
        receipt_for_validation = ExtractedReceipt.model_validate(
            {
                **corrected_receipt,
                "confidence": extracted_receipt.get("confidence", 0),
            },
        )
        claim_for_validation = {
            "claimed_amount": claim.claimed_amount,
            "claim_date": claim.claim_date,
            "currency": claim.currency,
        }
        validation_results = [
            result.model_dump(mode="json")
            for result in validate_claim(claim_for_validation, receipt_for_validation)
        ]
        with SessionLocal() as session:
            correction_claim = get_claim(session, claim.claim_id, employee_id)
            if correction_claim is None:
                st.error("Claim could not be found.")
                return
            update_receipt_correction(
                session,
                correction_claim,
                corrected_receipt,
                validation_results,
                corrected_by,
            )
            claim.corrected_by = correction_claim.corrected_by
            claim.corrected_at = correction_claim.corrected_at
            claim.corrected_validation_results = validation_results
        st.success("Verified receipt saved and validation checks rerun.")

    if corrected_receipt is not None:
        st.subheader("Verified Receipt")
        st.json(corrected_receipt)
        st.caption(
            f"Verified by {claim.corrected_by or employee_id or 'Finance Team'}"
            + (f" on {claim.corrected_at}" if claim.corrected_at is not None else ""),
        )


def _select_claim(employee_id: str | None, key: str) -> Claim | None:
    """Select and load an accessible claim."""
    with SessionLocal() as session:
        claims = list_claims(session, employee_id)
        claim_ids = [claim.claim_id for claim in claims]
    if not claim_ids:
        st.info("Submit a claim to view its details.")
        return None

    selected_id = st.selectbox("Claim ID", claim_ids, key=key)
    with SessionLocal() as session:
        claim = get_claim(session, selected_id, employee_id)
    if claim is None:
        st.error("Claim could not be found.")
    return claim


def _render_original_claim(claim: Claim) -> None:
    """Render the submitted claim fields."""
    st.subheader("Original Claim")
    st.json(
        {
            "claim_id": claim.claim_id,
            "employee_id": claim.employee_id,
            "employee_name": claim.employee_name,
            "department": claim.department,
            "claim_date": str(claim.claim_date),
            "expense_category": claim.expense_category,
            "expense_purpose": claim.expense_purpose,
            "claimed_amount": claim.claimed_amount,
            "currency": claim.currency,
        },
    )


def render_extraction_review_tab(employee_id: str | None = None) -> None:
    """Render receipt extraction review and correction."""
    st.header("Review Receipt Extraction")
    claim = _select_claim(employee_id, "extraction-review-claim")
    if claim is None:
        return

    _render_original_claim(claim)
    receipt_path = Path(claim.receipt_file_path)
    st.subheader("Receipt")
    if receipt_path.exists():
        st.image(str(receipt_path), width=500)
    else:
        st.warning("The saved receipt file is unavailable.")

    state = json.loads(claim.raw_agent_state or "{}")
    extracted_receipt = claim.extracted_receipt or state.get("extracted_receipt") or {}
    st.subheader("AI-Extracted Receipt")
    st.json(extracted_receipt)
    render_receipt_correction(claim, extracted_receipt, employee_id)


def render_claim_checks_tab(employee_id: str | None = None) -> None:
    """Render automated and corrected claim checks."""
    st.header("Claim Audit Trail")
    claim = _select_claim(employee_id, "claim-checks-claim")
    if claim is None:
        return

    state = json.loads(claim.raw_agent_state or "{}")
    _render_original_claim(claim)

    corrected_validation_results = getattr(
        claim,
        "corrected_validation_results",
        None,
    )
    if corrected_validation_results is not None:
        st.caption("Validation results use the verified receipt fields.")
        _render_checks(
            "Verified Validation Results",
            corrected_validation_results,
        )
    else:
        st.caption("Validation results use the original AI-extracted receipt.")
        _render_checks("Validation Results", state.get("validation_results", []))

    _render_checks("Policy Results", state.get("policy_results", []))
    _render_checks("Duplicate Check", state.get("duplicate_results", []))

    st.subheader("Final Decision")
    st.write(f"**{claim.decision or claim.status}**")
    st.write(claim.review_summary or "No summary recorded.")
    if claim.human_review_decision:
        st.caption(
            f"Human decision by {claim.human_reviewed_by or 'Reviewer Team'}"
            + (
                f" on {claim.human_reviewed_at}"
                if claim.human_reviewed_at is not None
                else ""
            ),
        )
        if claim.human_review_notes:
            st.write(claim.human_review_notes)

    st.subheader("Agent Review Trail")
    for step in state.get("agent_trail", []):
        st.write(f"**{step['agent']}**")
        st.write(step["message"])

    st.subheader("Langfuse")
    if claim.langfuse_trace_id:
        trace_url = get_trace_url(claim.langfuse_trace_id)
        if trace_url:
            st.link_button("Open Langfuse trace", trace_url)
        st.code(claim.langfuse_trace_id, language=None)
    else:
        st.write("No Langfuse trace was recorded.")

    with st.expander("Raw OCR Text"):
        st.code(state.get("raw_ocr_text") or "No OCR text recorded.", language=None)


st.set_page_config(page_title="Expense Claim Agent", page_icon="🧾", layout="wide")
st.markdown(
    """
    <style>
    [data-testid="stFileUploader"] button[aria-label="Add files"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
initialize_database()
st.title("Expense Claim Agent")
view = st.sidebar.selectbox("View as", ["Employee", "Reviewer Team"])

if view == "Employee":
    with SessionLocal() as session:
        employees = list_employees(session)
    employee = st.sidebar.selectbox(
        "Employee",
        employees,
        format_func=lambda item: item.employee_name,
    )
    st.sidebar.caption(f"Employee ID: {employee.employee_id}")
    submit_tab, dashboard_tab = st.tabs(["Submit Claim", "My Claims"])
    with submit_tab:
        render_submit_tab(employee)
    with dashboard_tab:
        render_dashboard_tab(employee.employee_id)
else:
    queue_tab, dashboard_tab, extraction_tab, checks_tab, policy_tab = st.tabs(
        [
            "Approval Queue",
            "Claims Dashboard",
            "Review Extraction",
            "Claim Audit Trail",
            "Review Rules",
        ],
    )
    with queue_tab:
        render_approval_queue_tab()
    with dashboard_tab:
        render_dashboard_tab()
    with extraction_tab:
        render_extraction_review_tab()
    with checks_tab:
        render_claim_checks_tab()
    with policy_tab:
        render_review_rules_tab()
