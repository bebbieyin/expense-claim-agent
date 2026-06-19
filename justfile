set dotenv-load := true

# Show the main workflow commands.
default:
    @echo "Main workflow:"
    @echo "  just setup          # install all development dependencies"
    @echo "  just run-ui         # run the expense claim UI"
    @echo "  just db-up          # start PostgreSQL"
    @echo "  just migrate        # apply database migrations"
    @echo "  just check          # run lint, security, and test checks"
    @echo "  just deploy-local   # rebuild and run with Docker"
    @echo "  just logs           # follow Docker logs"
    @echo "  just stop           # stop the Docker app"

# Install application and development dependencies.
setup:
    uv sync --all-groups
    pnpm install --frozen-lockfile

# Run the Streamlit application.
run-ui:
    uv run streamlit run app.py

# Start PostgreSQL for local development.
db-up:
    docker compose up -d db

# Apply all pending database migrations.
migrate:
    uv run alembic upgrade head

# Run all local quality checks.
check: lint security test

# Run Ruff lint and format checks.
lint:
    uv run --group lint ruff check .
    uv run --group lint ruff format --check .

# Run Bandit security checks.
security:
    uv run --group lint bandit -r src tests -s B101

# Run the test suite.
test:
    uv run --group test pytest

# Rebuild and run the app locally with Docker.
deploy-local: test
    docker compose up --build -d
    @echo "Streamlit UI: http://127.0.0.1:8501"

# Follow Docker Compose logs.
logs:
    docker compose logs -f ui db

# Stop the Dockerized application.
stop:
    docker compose down
