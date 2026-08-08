# Task ID: TASK-6.5: FreightSlip Ratecon PDF Parser & HITL Authorization

## Objective
Integrate the FreightSlip Rate Confirmation PDF parsing service into the Dispatch and Owner load creation forms, automatically extracting load metadata while enforcing a strict Human-in-the-Loop (HITL) authorization step before saving to SQLite.

## Target Files
- `src/ui/dispatch_view.py`
- `src/core/ratecon_parser.py` (or existing parser module)
- `src/core/services.py`
- `tests/test_end_to_end.py`
- `Tasks.md`

## Step-by-Step Requirements
1. **Ratecon PDF Upload Form:**
   - Add a **"📄 Import Rate Confirmation PDF (FreightSlip AI)"** file uploader in the Load Creation UI accepting `.pdf` documents.

2. **Parsing & Form Auto-Fill Engine:**
   - Parse uploaded PDFs to extract key load parameters:
     * **Broker / Shipper Name**
     * **Rate ($ Payout)**
     * **Pickup Location & Date**
     * **Delivery Location & Date**
     * **Commodity / Weight / Reference #**
   - Pre-populate all matching input fields in the Load Creation form with extracted metadata.

3. **Human-in-the-Loop (HITL) Authorization Guardrail:**
   - **DO NOT** commit parsed load data automatically to the database.
   - Display a bold yellow verification banner:
     > **⚠️ Verify Extracted FreightSlip Data:** *Please inspect all auto-filled fields against your original PDF rate confirmation before authorizing.*
   - Require explicit user click on a **"✅ Authorize & Commit Load"** button to execute the database write.

4. **Automated Verification:**
   - Add pytest coverage testing PDF text parsing, form auto-fill, and human authorization guards.
   - Run `venv/bin/python -m pytest` to verify all 76+ tests pass green.

## Guardrails & Verification
- Prevent zero-click database insertions on PDF uploads.
- Run `git add . && git commit -m "feat(dispatch): integrate FreightSlip ratecon parser with HITL authorization" && git push origin main`.