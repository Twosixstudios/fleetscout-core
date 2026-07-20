# Phase 2: Backend API, Security Core & Access Routing

## Model Assignment
* **Primary Engine:** qwen2.5-code (Local via Ollama)
* **Execution Focus:** Build out secure, authenticated API endpoints, handle cryptographic tokens, and prepare data routers for the Streamlit frontend presentation layer.

## Architecture Standards
* **Modularity:** Maintain strict separation between database data models (`src/core`), route logic (`src/api`), and user-facing presentation tools.
* **Human-in-the-Loop Validation:** NEVER automatically refactor code or re-run test scripts in an autonomous loop if an execution fails. If a test fails, halt immediately, present the traceback log to the Flight Director, and wait for explicit diagnostic clearance.
* **Security First:** Ensure all endpoint logic routes through our verified, native `bcrypt` hashing utilities and async token dependency checks.