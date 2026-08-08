# Task ID: TASK-6.3: Admin Controls, Dispatcher Recovery, & Email Onboarding Invitations

## Objective
Build comprehensive account administration for Owners (Edit User, Password Overrides, Deactivation), password recovery tools for Dispatchers, and an Email Onboarding Invitation System so recruits can set up their accounts prior to Day 1.

## Target Files
- `src/ui/owner_portal.py`
- `src/ui/dispatch_view.py`
- `src/core/services.py`
- `src/core/models.py`
- `app.py`
- `tests/test_end_to_end.py`
- `Tasks.md`

## Step-by-Step Requirements
1. **Invite Token Schema & Services (`src/core/models.py` & `src/core/services.py`):**
   - Add `UserInvite` database model (or token table) storing: `email`, `role`, `carrier_id`, `token`, `status` (`Pending`/`Accepted`), and `expires_at`.
   - Implement `create_onboarding_invite(db: AsyncSession, carrier_id: int, email: str, role: str)`:
     * Generates a unique token and records the pending invite.
     * Simulates/dispatches the onboarding email payload containing the registration link.
   - Implement `accept_onboarding_invite(db: AsyncSession, token: str, username: str, password: str)`:
     * Validates token, hashes password, creates active `User` bound to `carrier_id`, and marks invite as `Accepted`.

2. **Backend Admin & Reset Overrides (`src/core/services.py`):**
   - Implement `admin_reset_password(db: AsyncSession, target_user_id: int, new_password: str, carrier_id: int)`.
   - Implement `update_team_member(db: AsyncSession, target_user_id: int, username: str, email: str, role: str, carrier_id: int)`.
   - Implement `toggle_user_active_status(db: AsyncSession, target_user_id: int, active_status: bool, carrier_id: int)` (prevents self-deactivation).

3. **Owner Portal & Dispatcher UI Upgrades (`src/ui/owner_portal.py` & `src/ui/dispatch_view.py`):**
   - **Send Onboarding Invite Form:** Form to send email invitations to new hires with a "Pending Invitations" status list.
   - **Interactive Team Roster Controls:** 
     * **Edit Details:** Modal/expander to update user name, email, or role.
     * **Reset Password:** Instant override form for Owners/Dispatchers to set a temporary password or generate a recovery PIN.
     * **Deactivate / Reactivate Toggle:** One-click account access switch.

4. **Public Onboarding Redemption View in `app.py`:**
   - Detect invite tokens via URL params (e.g. `?invite_token=XYZ`) or a "Redeem Invite" screen on the login page where recruits complete registration.

5. **Automated Verification:**
   - Add end-to-end tests covering invite generation, token redemption, user edits, password overrides, and account deactivation.
   - Run `venv/bin/python -m pytest` to confirm all test suites pass green.

## Guardrails & Verification
- Strict `carrier_id` isolation: Owners and Dispatchers can only invite, edit, or reset users within their own carrier network.
- Run `git add . && git commit -m "feat(admin): add employee email onboarding invites, admin edit controls, and dispatcher recovery tools" && git push origin main` upon successful completion.