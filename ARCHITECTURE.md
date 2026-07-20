# Project Architecture & Standards

## Tech Stack
- **Framework:** FastAPI (Asynchronous ASGI execution engine)
- **Database Layer:** SQLAlchemy ORM utilizing an asynchronous engine workflow
- **Database Driver:** aiosqlite (Asynchronous SQLite)

## Critical Coding Standards
1. **Strictly Asynchronous Execution:** Traditional synchronous database patterns (e.g., 'create_all(bind=engine)') are strictly prohibited.
2. **Schema Control:** All structural schema initializations must happen safely within async connection loops ('engine.begin()') inside lifecycle event hooks.
3. **No Code Snippet Mixing:** Do not introduce synchronous code paradigms into modular source files. Cross-reference edits against existing configuration files to preserve consistency.