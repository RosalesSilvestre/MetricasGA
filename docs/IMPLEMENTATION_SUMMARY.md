# Implementation Summary: Staging Workflow for Current Month Monitoring

## ✅ Completed Changes

### 1. Code Review & Bug Fixes

#### Fixed Logic Error in `main.py`
- **Issue**: Lines 69-74 had incorrect conditional logic for carreras property ID selection
- **Fix**: Corrected the logic to properly validate and set the appropriate property ID based on date
- **Impact**: Prevents potential runtime errors when fetching carreras.itam.mx data

### 2. `main.py` Refactoring

#### Added Features:
- ✅ `argparse` integration with `--mode` flag
- ✅ Two modes:
  - `historical` (default): Fetches previous month's finalized data → saves to `historical/`
  - `current`: Fetches current month progress (1st to yesterday) → saves to `staging/current_month_progress.csv`
- ✅ Automatic folder creation for `staging/` directory
- ✅ Staging file overwrites on each run (prevents accumulation)

#### Usage:
```bash
# Historical mode (default)
python main.py
# or explicitly
python main.py --mode historical

# Current month mode
python main.py --mode current
```

### 3. `sheets_v2.py` Refactoring

#### Added Features:
- ✅ New function `load_staging_data()`: Reads from `staging/current_month_progress.csv`
- ✅ New function `update_current_month_tab()`: Updates "Current Month" tab with raw metrics
- ✅ Modified `update_google_sheet()`: Now accepts `sheet_name` parameter
- ✅ Automatic sheet tab creation if "Current Month" doesn't exist
- ✅ `main()` function now accepts `mode` parameter
- ✅ `argparse` integration for command-line mode selection

#### Data Processing:
- **Historical mode**: Full YTD/YoY calculations → "Analytics" tab
- **Current mode**: Raw metrics only (Date, Metric, Value) → "Current Month" tab

#### Usage:
```bash
# Historical mode (default)
python sheets_v2.py
# or explicitly
python sheets_v2.py --mode historical

# Current month mode
python sheets_v2.py --mode current
```

### 4. `upload_to_mysql.py` Safeguards

#### Added Safeguards:
- ✅ Explicit validation that only `historical/` folder is processed
- ✅ Warning messages if staging files are detected
- ✅ Explicit rejection of any paths containing "staging"
- ✅ Clear logging to indicate staging files are ignored

#### Data Integrity:
- ✅ **Guaranteed**: Staging data NEVER goes to MySQL
- ✅ **Guaranteed**: Only finalized historical data is uploaded

---

## 📁 File Structure

```
MetricasGA/
├── historical/                    # Finalized monthly snapshots
│   └── results_YYYY-MM-DD.csv
├── staging/                      # NEW: Current month progress
│   └── current_month_progress.csv (overwrites on each run)
├── main.py                       # MODIFIED: Added --mode flag
├── sheets_v2.py                  # MODIFIED: Added staging support
└── upload_to_mysql.py            # MODIFIED: Added safeguards
```

---

## 🔄 Workflow Examples

### Weekly Current Month Update (for business users)
```bash
# Step 1: Fetch current month data (1st to yesterday)
python main.py --mode current

# Step 2: Update "Current Month" tab in Google Sheets
python sheets_v2.py --mode current
```

### Monthly Historical Finalization (end of month)
```bash
# Step 1: Fetch previous month's finalized data
python main.py --mode historical

# Step 2: Calculate YTD/YoY and update "Analytics" tab
python sheets_v2.py --mode historical

# Step 3: Upload to MySQL (only reads from historical/)
python upload_to_mysql.py
```

---

## 🛡️ Data Integrity Guarantees

1. **Staging data NEVER goes to MySQL**
   - `upload_to_mysql.py` explicitly filters out staging folder
   - Multiple validation checks prevent accidental staging uploads

2. **Staging data NEVER goes to historical**
   - `main.py` routes data based on mode flag
   - Different folder structures prevent mixing

3. **Current Month tab is separate**
   - Different tab name ("Current Month" vs "Analytics")
   - Different data structure (raw metrics vs calculated metrics)

4. **Staging file overwrites**
   - Prevents accumulation of partial data files
   - Always represents the latest current month progress

---

## 📊 Google Sheets Structure

After implementation, your Google Sheet will have two tabs:

1. **"Analytics"** tab:
   - Finalized monthly data
   - Includes YTD and YoY calculations
   - Updated monthly with historical data

2. **"Current Month"** tab (NEW):
   - Current month progress (1st to yesterday)
   - Raw metrics only (Date, Metric, Value)
   - Updated weekly/daily as needed
   - No YTD/YoY calculations

---

## ⚠️ Important Notes

1. **Run order matters**: Always run `main.py` before `sheets_v2.py` to ensure data exists
2. **Staging folder**: Will be created automatically if it doesn't exist
3. **Sheet tab creation**: "Current Month" tab will be created automatically if it doesn't exist
4. **Date format**: All dates are in 'YYYY-MM-DD' format
5. **Overwrite behavior**: Staging file is overwritten on each run (by design)

---

## 🧪 Testing Recommendations

1. Test current mode with a small date range
2. Verify "Current Month" tab is created and populated correctly
3. Verify "Analytics" tab remains unchanged when running current mode
4. Verify MySQL upload ignores staging folder
5. Test error handling when staging file doesn't exist

---

## 📝 Next Steps (Optional Enhancements)

1. Add error handling for API quota limits
2. Add logging to file for audit trail
3. Add email notifications for failed runs
4. Add data validation before sheet updates
5. Consider adding a "Last Updated" timestamp to sheets

