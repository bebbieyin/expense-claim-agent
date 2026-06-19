"""Streamlit interface for the Phase 1 expense claim review app."""

import json
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st
from sqlalchemy import func, select

from src.database.entities import Claim, Employee
from src.database.operations import (
    SessionLocal,
    create_claim,
    get_claim,
    list_claims,
    list_employees,
    run_migrations,
    update_claim_review,
)
from src.shared.schemas import ClaimCreate
from src.shared.utils import next_claim_id, save_uploaded_receipt
from src.workflow.agents import run_review

EXPENSE_CATEGORIES = ["Meals", "Transport", "Office Supplies", "Medical"]
DEPARTMENTS = ["Sales & Marketing", "IT", "HR", "Finance", "Operations"]


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


def render_submit_tab(employee: Employee) -> None:
    """Render and process the expense submission form."""
    st.header("Submit Expense Claim")
    st.caption(
        "Phase 1 uses a mock receipt extraction: Restoran ABC, 2026-06-16, MYR 45.90.",
    )
    st.text_input("Employee ID", value=employee.employee_id, disabled=True)

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
        receipt = st.file_uploader(
            "Receipt image",
            type=["png", "jpg", "jpeg", "webp"],
        )
        submitted = st.form_submit_button("Submit & Review", type="primary")

    if not submitted:
        return
    required_fields = [department, purpose]
    if not all(value.strip() for value in required_fields):
        st.error("Complete all text fields before submitting.")
        return
    if receipt is None:
        st.error("Upload a receipt image before submitting.")
        return

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
            session.commit()
            st.error(f"Claim {claim.claim_id} was stored, but review failed.")
            return

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


def render_detail_tab(employee_id: str | None = None) -> None:
    """Render an accessible claim review record."""
    st.header("Claim Detail")
    with SessionLocal() as session:
        claims = list_claims(session, employee_id)
        claim_ids = [claim.claim_id for claim in claims]
    if not claim_ids:
        st.info("Submit a claim to view its details.")
        return

    selected_id = st.selectbox("Claim ID", claim_ids)
    with SessionLocal() as session:
        claim = get_claim(session, selected_id, employee_id)
    if claim is None:
        st.error("Claim could not be found.")
        return

    state = json.loads(claim.raw_agent_state or "{}")
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

    receipt_path = Path(claim.receipt_file_path)
    st.subheader("Receipt")
    if receipt_path.exists():
        st.image(str(receipt_path), width=500)
    else:
        st.warning("The saved receipt file is unavailable.")

    st.subheader("Extracted Receipt")
    st.json(state.get("extracted_receipt") or {})
    _render_checks("Validation Results", state.get("validation_results", []))
    _render_checks("Policy Results", state.get("policy_results", []))
    _render_checks("Duplicate Check", state.get("duplicate_results", []))

    st.subheader("Final Decision")
    st.write(f"**{claim.decision or claim.status}**")
    st.write(claim.review_summary or "No summary recorded.")

    st.subheader("Agent Review Trail")
    for step in state.get("agent_trail", []):
        st.write(f"**{step['agent']}**")
        st.write(step["message"])

    st.subheader("Langfuse")
    st.write(claim.langfuse_trace_id or "Not connected in Phase 1.")


st.set_page_config(page_title="Expense Claim Agent", page_icon="🧾", layout="wide")
run_migrations()
st.title("Expense Claim Agent")
view = st.sidebar.selectbox("View as", ["Employee", "Finance Team"])

if view == "Employee":
    with SessionLocal() as session:
        employees = list_employees(session)
    employee = st.sidebar.selectbox(
        "Employee",
        employees,
        format_func=lambda item: item.employee_name,
    )
    st.sidebar.caption(f"Employee ID: {employee.employee_id}")
    submit_tab, dashboard_tab, detail_tab = st.tabs(
        ["Submit Claim", "My Claims", "Claim Detail"],
    )
    with submit_tab:
        render_submit_tab(employee)
    with dashboard_tab:
        render_dashboard_tab(employee.employee_id)
    with detail_tab:
        render_detail_tab(employee.employee_id)
else:
    dashboard_tab, detail_tab = st.tabs(["Claims Dashboard", "Claim Detail"])
    with dashboard_tab:
        render_dashboard_tab()
    with detail_tab:
        render_detail_tab()
