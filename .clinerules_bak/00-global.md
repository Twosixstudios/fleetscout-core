# TwoSixStudios Global Project Constraints

## Core Standards
* **Project Scope:** Architectural blueprints must prioritize application builds that are clean, verifiable, and structured for local hosting.
* **Network & Data:** Maintain strict local-first processing paths.
* **Agent Behavior:** Never execute multi-file changes or delete structural components without displaying a summary blueprint for approval first.

## ⚡ Execution Laws
* **The Pytest Command Law:** ALWAYS run tests using `python -m pytest`. Never run raw `pytest` commands.
* **The Seed Command Law:** ALWAYS run seeds using `python -m src.core.seed`.

## 🛡️ Backend & Security Architecture Rules
* **Native Bcrypt Only:** Use native `bcrypt` for password hashing and verification. DO NOT install or reference `passlib`.
* **Async Integrity:** All database operations use `AsyncSession`. Do not mix synchronous FastAPI execution clients with async SQLAlchemy loops.

## 📋 Operational Protocol
* **The Blueprint Rule:** Before executing file-write tools or modifying code, output a concise 3-bullet blueprint detailing proposed changes, file paths, and preserved code.
* **Schema Verification Rule:** Inspect `src/core/models.py` before writing frontend code to ensure column names exist on disk.