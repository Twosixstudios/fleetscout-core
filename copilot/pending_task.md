# Task ID: DOCS-5.6: Install Global Agent Rules & Sync Phase 5 Status

## Objective
Update `CLAUDE.md` to establish universal, dynamic agent rules of engagement (removing hardcoded phase references) and sync `Tasks.md` to mark Phase 5 at 100% completion.

## Target Files
- `CLAUDE.md`
- `Tasks.md`

## Step-by-Step Requirements
1. **Install Dynamic Rules in CLAUDE.md:**
   - Replace the static rules in `CLAUDE.md` with the universal **Agent Rules of Engagement** (mandating dynamic status updates for task checkboxes, header progress, and active phase transitions).
   - Set the current **Active Phase** line in `CLAUDE.md` to: `Phase 5 - Modular Plugins, Hardening & Deploy (Completed)`

2. **Sync Tasks.md Headers:**
   - Update `Tasks.md` **Current Status** header:
     * Active Phase: `Phase 5 - Modular Plugins, Hardening & Deploy`
     * Overall Progress: `4 / 4 Tasks Completed (100%)`
   - Verify all tasks from Phase 1 through Phase 5 (Tasks 1.1–1.4, 2.1–2.3, 3.1–3.4, 4.1–4.4, 5.1–5.4) are marked `[x]`.

## Guardrails & Verification
- Do not modify application code inside `src/` or `tests/`.
- Ensure markdown formatting in both files remains clean and easy for LLMs to parse.
- Run `git add . && git commit -m "docs: install global agent rules and set Phase 5 status to 100%" && git push origin main` upon successful verification.