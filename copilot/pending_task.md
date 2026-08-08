# Task ID: TASK-6.3: Executive Owner Dashboard & Complete Account Controls

## Objective
Replace the sidebar hat-switcher with an intuitive, tabbed Executive Owner Dashboard, add full user account deletion/deactivation controls, password overrides, and onboarding email invitations.

## Target Files
- `src/ui/owner_portal.py`
- `app.py`
- `src/core/services.py`
- `tests/test_end_to_end.py`
- `Tasks.md`

## Step-by-Step Requirements
1. **Executive Dashboard Redesign (`src/ui/owner_portal.py` & `app.py`):**
   - Remove the clunky "Hat-Switcher" radio buttons from the sidebar.
   - Restructure `Owner View` into an Executive Navigation bar/tab system:
     * **📊 Fleet Command Center:** Real-time active loads, dispatch map, and vehicle statuses.
     * **🚛 Driver Console View:** Direct view of driver mobile status, duty clock, and repair forms for solo owner-operators.
     * **👥 Team & Access Management:** Unified team roster, user creation, account deletion, and onboarding invites.
     * **⚙️ Carrier Settings:** White-label branding, carrier name, and DOT details.

2. **Full User Account Controls & Deactivation (`src/core/services.py`):**
   - Implement `delete_or_deactivate_user(db: AsyncSession, target_user_id: int, carrier_id: int)`:
     * Deactivates/removes the target user while maintaining database integrity for historical trip logs.
     * Protects the Owner from deleting their own account.
   - Add **Action Column** in the Team Roster table with:
     * **🗑️ Delete / Remove:** Permanently revokes access.
     * **🔑 Reset Password:** Direct password override modal.
     * **✏️ Edit Details:** Update username or email.

3. **Email Onboarding Invite System:**
   - Add a "Send Onboarding Invite" tab to issue invite tokens to new recruits before their Day 1 start.

4. **Automated Verification:**
   - Add end-to-end tests for account deletion, tab navigation, and password overrides.
   - Run `venv/bin/python -m pytest` to confirm all test suites pass cleanly.

## Guardrails & Verification
- Strict `carrier_id` boundary checks on all delete/edit actions.
- Run `git add . && git commit -m "feat(owner): executive dashboard UI overhaul with user deletion and onboarding tools" && git push origin main` upon completion.