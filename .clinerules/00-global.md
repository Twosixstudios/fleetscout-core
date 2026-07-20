# TwoSixStudios Global Project Constraints

## Core Standards
* **Project Scope:** Architectural blueprints must prioritize application builds that are clean, verifiable, and structured for local hosting.
* **Network & Data:** Maintain strict local-first processing paths across the linked network interface.
* **Agent Behavior:** Never execute multi-file changes or delete structural components without displaying a comprehensive file-diff for human approval first.

## � Phase 2 Active Execution Laws (Access & Routing)
* **The Pytest Command Law:** ALWAYS run tests using `python -m pytest`. Never run raw `pytest` commands, as local path modules will fail to resolve.
* **The Token Firewall:** Keep test executions highly targeted (e.g., `python -m pytest tests/test_auth.py -v`). Do not dump massive unformatted logs into the stream to save context memory.

## �️ Backend & Security Architecture Rules
* **Native Bcrypt Only:** Use native `bcrypt` for all password hashing and verification. Absolutely DO NOT install, import, or reference `passlib` due to upstream binary conflicts with bcrypt 5.0.0+.
* **Async Integrity:** All database operations use `AsyncSession`. Do not mix synchronous FastAPI execution clients with async SQLAlchemy loops without a properly scoped async loop fixture.
* **No Phantom Code:** Do not write phantom endpoints or validation tests for routes that have not been explicitly declared in the active milestone checklist.

## � Multi-Model AI Routing (Future Phases)
* **Gemma4:12b Reserve:** Gemma (running locally via Ollama) is designated as the Chief Architect for future document scanning, receipt processing, and camera logging modules.
* **Cline Constraint:** Do not attempt to prototype standalone OCR libraries or write custom vision-parsing logic for the media stack. All document and camera data streams will be routed directly to the local Gemma node in later phases.

## � Operational Protocol (The Blueprint Rule)
* **The Prompt Handshake:** Before executing ANY file-write tool or modifying code, you MUST output a concise, 3-bullet blueprint detailing your proposed changes, exact file paths, and what existing code is being preserved.
* **Explicit Clearance Required:** You MUST wait for explicit user confirmation/approval before proceeding to edit or write any files.

### �️ Schema Verification Rule- Before modifying or generating any frontend code (such as `app.py`), inspect `src/core/models.py` and `src/core/database.py` to verify that all imported SQLAlchemy classes, helper functions, and column names exist on disk. Never assume legacy frontend imports or schemas are valid.