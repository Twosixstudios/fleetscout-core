# Task ID: TASK-6.2: Owner Team Provisioning Engine

## Objective
Build a user creation engine inside the Owner Portal (`src/ui/owner_portal.py`) that allows Fleet Owners to provision new Dispatcher and Driver accounts directly from the UI, hash their passwords, and immediately attach them to their `carrier_id`.

## Target Files
- `src/ui/owner_portal.py`
- `src/core/services.py`
- `tests/test_end_to_end.py`
- `Tasks.md`

## Step-by-Step Requirements
1. **User Provisioning Service (`src/core/services.py`):**
   - Implement an async function `create_team_member(db: AsyncSession, carrier_id: int, email: str, username: str, password: str, role: str)`:
     * Validates that `role` is either `Dispatcher` or `Driver`.
     * Hashes the password using `get_password_hash()`.
     * Checks for duplicate email/username and raises a user-friendly error if already taken.
     * Inserts the new `User` record bound to `carrier_id` and commits.

2. **Team Provisioning Form (`src/ui/owner_portal.py`):**
   - Add a **"➕ Provision New Team Member"** form/expander in the Owner Portal.
   - Include input fields:
     * **Email Address** (`email_input`)
     * **Username / Name** (`username_input`)
     * **Temporary Password** (`password_input`)
     * **Assigned Role** (`role_selectbox` with options: `Dispatcher`, `Driver`)
   - Handle form submission with defensive error catching (`st.success` on success, `st.error` on duplicate email/validation failures).
   - Trigger a live rerun (`st.rerun()`) upon successful creation so the **Team Roster** table updates instantly.

3. **Automated Verification:**
   - Add end-to-end pytest coverage verifying that an Owner can successfully provision a new Driver and Dispatcher and that duplicates are blocked.
   - Run `venv/bin/python -m pytest` to confirm all 61+ tests pass.

## Guardrails & Verification
- Ensure all new users are strictly assigned to the active Owner's `carrier_id`.
- Run `git add . && git commit -m "feat(owner): add team provisioning engine for dispatchers and drivers" && git push origin main` upon successful verification.