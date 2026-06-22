# Refactoring Plan: Staging Workflow for Current Month Monitoring

## Code Review Findings

### Issues Identified:

1. **Logic Error in `main.py` (lines 69-74)**: 
   - There's a bug in the carreras property logic. If `ITAM_CARRERAS_GA4_PROPERTY_ID_NEW` is not set, the code incorrectly tries to set `properties['carreras.itam.mx']` again in the else block.
   - **Fix**: Correct the conditional logic to properly handle both old and new property IDs.

2. **Redundant Code**:
   - The `update_google_sheet()` function in `main.py` (lines 245-321) appears redundant since `sheets_v2.py` handles all Google Sheets updates.
   - **Action**: Keep it for now but note it may be unused in the main workflow.

3. **Fiscal Year Calculation**:
   - The fiscal year calculation in `sheets_v2.py` is correct (August-based fiscal year starting in month >= 8).
   - No changes needed.

### API Quota Considerations:
- The current implementation makes multiple API calls per run. The staging workflow will add one more run per week, which should be manageable.

---

## Implementation Plan

### 1. `main.py` Modifications

**Changes:**
- Add `argparse` to accept a `--mode` flag with options: `historical` (default) or `current`
- When `--mode current`:
  - Calculate date range: 1st of current month to yesterday
  - Save output to `staging/current_month_progress.csv` (overwrite existing)
  - Ensure `staging/` folder exists
- When `--mode historical` (default):
  - Keep existing behavior (save to `historical/` folder)
- Fix the carreras property logic bug

**Data Flow:**
```
--mode historical → historical/results_YYYY-MM-DD.csv
--mode current → staging/current_month_progress.csv (overwrites)
```

### 2. `sheets_v2.py` Modifications

**Changes:**
- Add a new function `load_staging_data()` to read from `staging/current_month_progress.csv`
- Add a new function `update_current_month_tab()` to update the "Current Month" tab
- Modify `main()` to accept a parameter indicating which mode to run
- For staging data:
  - Skip YoY/YTD calculations (just show raw metrics)
  - Update "Current Month" tab instead of "Analytics" tab
- For historical data:
  - Keep existing behavior (update "Analytics" tab with calculated metrics)

**Data Processing:**
- Historical mode: Full YTD/YoY calculations → "Analytics" tab
- Staging mode: Raw metrics only → "Current Month" tab

### 3. `upload_to_mysql.py` Modifications

**Changes:**
- Add explicit check in `find_new_files()` to ensure it ONLY searches in `historical/` folder
- Add validation to reject any files from `staging/` folder if accidentally passed
- Add logging to clearly indicate it's ignoring staging folder

**Safeguards:**
- Explicitly filter out any paths containing "staging"
- Add warning message if staging files are detected

---

## File Structure After Changes

```
MetricasGA/
├── historical/          # Finalized monthly snapshots (unchanged)
│   └── results_YYYY-MM-DD.csv
├── staging/            # NEW: Current month progress (overwrites)
│   └── current_month_progress.csv
├── main.py             # MODIFIED: Added --mode flag
├── sheets_v2.py        # MODIFIED: Added staging support
└── upload_to_mysql.py  # MODIFIED: Added staging safeguards
```

---

## Execution Workflow

### Weekly Current Month Update:
```bash
python main.py --mode current
python sheets_v2.py --mode current
```

### Monthly Historical Finalization:
```bash
python main.py --mode historical  # or just python main.py
python sheets_v2.py --mode historical  # or just python sheets_v2.py
python upload_to_mysql.py
```

---

## Data Integrity Guarantees

1. **Staging data NEVER goes to MySQL**: `upload_to_mysql.py` explicitly filters out staging folder
2. **Staging data NEVER goes to historical**: `main.py` routes based on mode flag
3. **Current Month tab is separate**: Different tab name prevents mixing with finalized data
4. **Staging file overwrites**: Prevents accumulation of partial data files

