@get_credentials.py @main.py @sheets_v2.py @upload_to_mysql.py

You are an expert Senior Data Engineer and Python Developer. I need you to refactor the current ETL system to add a specific monitoring feature without compromising data integrity.

### System Overview
- **Extraction (`main.py`):** Fetches GA4 and YouTube metrics. Currently saves monthly snapshots to `historical/`.
- **Transformation/Load (`sheets_v2.py`):** Calculates metrics (YTD, YoY) and updates a Google Sheet.
- **Persistence (`upload_to_mysql.py`):** Uploads finalized monthly CSVs to MySQL.

### The New Requirement
The business user needs **weekly visibility of the current month's performance**.
- They want to see "Month-to-Date" data for the current month.
- This data must reside in the **same Google Sheet** but in a **new, separate tab** (e.g., named "Current Month").
- **CRITICAL:** This partial data must NEVER be mixed with the finalized historical data in the `historical/` folder or the MySQL database.

### Task List

#### 1. Code Review & Optimization
First, analyze the provided scripts.
- Check for logic errors, especially in `sheets_v2.py` regarding fiscal year calculations.
- Identify redundant code or potential API quota risks.
- Propose fixes for any immediate issues found.

#### 2. Implementation: Staging Strategy
Refactor the system to handle a "Staging" workflow:
- **`main.py`**:
    - Implement `argparse` to accept a flag (e.g., `--mode current`).
    - When in `current` mode, fetch data from the 1st of the current month up to yesterday.
    - **Output:** Save this file to a new folder named `staging/` (e.g., `staging/current_month_progress.csv`). Do NOT save it to `historical/`.
    - Ensure the script overwrites this specific file every time it runs to avoid clutter.

- **`sheets_v2.py`**:
    - Add functionality to read from `staging/`.
    - Create a function to update a specific tab in Google Sheets.
    - If reading from `staging`, target a new sheet tab named "Current Month".
    - **Note:** For the "Current Month" tab, we probably don't need YoY or YTD comparisons against previous years, just the raw metrics for the current period. Adjust the processing logic accordingly.

- **`upload_to_mysql.py`**:
    - Add a safeguard to explicitly verify it ONLY reads from `historical/` and ignores `staging/`.

### Deliverable
1. **Plan:** Briefly explain how you will modify the logic in `main.py` and `sheets_v2.py` to handle the routing of data (Historical vs. Staging).
2. **Code:** Generate the refactored code.

Please proceed with the Plan first.