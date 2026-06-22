import os
import argparse
import glob
import pandas as pd
import numpy as np # <--- SE AGREGA LA IMPORTACIÓN DE NUMPY
import dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables from .env file
dotenv.load_dotenv()

# This dictionary should be consistent with the one in main.py
METRICS_DICT = {
    1: "ITAM Total Users",
    2: "ITAM Views",
    3: "ITAM Views Per Session",
    4: "Blog Total Users",
    5: "Blog Views",
    6: "Blog Views Per Session",
    7: "Carreras Total Users",
    8: "Carreras Views",
    9: "Carreras Views Per Session",
    10: "YouTube Advertisement Views",
    11: "YouTube Organic Views",
    12: "YouTube Total Views"
}

def load_historical_data(folder_path='historical'):
    """
    Loads and consolidates all historical metric CSVs from a specified folder.
    """
    csv_files = glob.glob(os.path.join(folder_path, 'results_*.csv'))
    if not csv_files:
        print(f"Warning: No historical data files found in '{folder_path}'.")
        return pd.DataFrame()

    df_list = [pd.read_csv(file) for file in csv_files]
    df = pd.concat(df_list, ignore_index=True)

    df['Date'] = pd.to_datetime(df['Date'])
    df['Metric'] = df['Metric'].map(METRICS_DICT)
    df.dropna(subset=['Metric'], inplace=True)
    df.sort_values(by=['Metric', 'Date'], inplace=True)
    
    return df

def load_staging_data(file_path='staging/current_month_progress.csv'):
    """
    Loads current month progress data from staging folder.
    Returns a DataFrame with raw metrics (no YTD/YoY calculations).
    """
    if not os.path.exists(file_path):
        print(f"Warning: Staging file '{file_path}' not found.")
        return pd.DataFrame()
    
    df = pd.read_csv(file_path)
    df['Date'] = pd.to_datetime(df['Date'])
    df['Metric'] = df['Metric'].map(METRICS_DICT)
    df.dropna(subset=['Metric'], inplace=True)
    
    # For staging data, we'll keep it simple - just Date, Metric, Value
    # No YTD/YoY calculations needed for current month progress
    return df

def calculate_advanced_metrics(df):
    """
    Calculates YTD based on a fiscal year starting in August and fetches 
    the corresponding values from the previous year.
    """
    if df.empty:
        return df

    # <--- CAMBIO CLAVE: Determinar el año fiscal ---
    # Si el mes es >= 8 (Agosto), el año fiscal es el año actual.
    # Si no, el año fiscal es el año anterior.
    df['fiscal_year'] = np.where(df['Date'].dt.month >= 8, 
                                df['Date'].dt.year, 
                                df['Date'].dt.year - 1)

    # <--- CAMBIO CLAVE: Usar el año fiscal para agrupar y calcular el YTD ---
    # La suma acumulada (cumsum) ahora se reiniciará cada agosto.
    df['ytd'] = df.groupby(['Metric', 'fiscal_year'])['Value'].cumsum()

    # Los cálculos de YoY no cambian, ya que se basan en un desplazamiento de 12 meses
    df['year_over_year'] = df.groupby('Metric')['Value'].shift(12)
    df['ytd_over_year'] = df.groupby('Metric')['ytd'].shift(12)

    # Se mantiene el resto de la función para limpiar y dar formato
    final_df = df[[
        'Date', 'Metric', 'Value', 'ytd', 'year_over_year', 'ytd_over_year'
    ]].copy()
    
    final_df['Date'] = final_df['Date'].dt.strftime('%Y-%m-%d')
    
    return final_df

def update_google_sheet(df, sheet_name="Analytics"):
    """
    Clears and updates a Google Sheet with the final calculated data.
    
    Args:
        df: DataFrame to upload
        sheet_name: Name of the sheet tab to update (default: "Analytics")
    """
    if df.empty:
        print("Dataframe is empty, skipping Google Sheet update.")
        return
        
    try:
        GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
        GOOGLE_SHEETS_CREDENTIALS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")

        if not all([GOOGLE_SHEET_ID, GOOGLE_SHEETS_CREDENTIALS_PATH]):
            raise ValueError("Google Sheet environment variables are not set.")

        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_SHEETS_CREDENTIALS_PATH,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()

        # Check if sheet tab exists, create if it doesn't
        try:
            spreadsheet = sheet.get(spreadsheetId=GOOGLE_SHEET_ID).execute()
            sheet_names = [s['properties']['title'] for s in spreadsheet.get('sheets', [])]
            
            if sheet_name not in sheet_names:
                print(f"Creating new sheet tab: '{sheet_name}'...")
                requests = [{
                    'addSheet': {
                        'properties': {
                            'title': sheet_name
                        }
                    }
                }]
                sheet.batchUpdate(spreadsheetId=GOOGLE_SHEET_ID, body={'requests': requests}).execute()
        except Exception as e:
            print(f"Warning: Could not verify/create sheet tab: {e}")

        df.fillna('', inplace=True)
        values_to_upload = [df.columns.tolist()] + df.values.tolist()

        print(f"Clearing existing data from sheet: '{sheet_name}'...")
        sheet.values().clear(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=sheet_name
        ).execute()

        print(f"Writing {len(df)} rows of new data to the sheet...")
        body = {'values': values_to_upload}
        result = sheet.values().update(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=f"{sheet_name}!A1",
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        
        print(f"✅ Success! {result.get('updatedCells')} cells updated in Google Sheet '{sheet_name}'.")

    except HttpError as err:
        print(f"❌ An API error occurred: {err}")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")

def update_current_month_tab(df):
    """
    Updates the "Current Month" tab with raw metrics (no YTD/YoY calculations).
    This is for staging data showing current month progress.
    """
    if df.empty:
        print("Dataframe is empty, skipping Current Month tab update.")
        return
    
    # Prepare simple DataFrame with just Date, Metric, Value
    simple_df = df[['Date', 'Metric', 'Value']].copy()
    simple_df['Date'] = simple_df['Date'].dt.strftime('%Y-%m-%d')
    
    update_google_sheet(simple_df, sheet_name="Current Month")

def main(mode='historical'):
    """
    Main execution function to orchestrate data loading, calculation,
    and updating the sheet.
    
    Args:
        mode: 'historical' for finalized monthly data with YTD/YoY,
              'current' for current month progress (raw metrics only)
    """
    if mode == 'current':
        print("🔄 Starting Current Month update process...")
        
        # Load staging data (current month progress)
        staging_df = load_staging_data()
        if staging_df.empty:
            print("No staging data found. Make sure to run 'main.py --mode current' first.")
            return
        
        # Update Current Month tab with raw metrics
        update_current_month_tab(staging_df)
        print("✨ Current Month update complete.")
        
    else:  # historical mode
        print("🚀 Starting metrics aggregation process...")
        
        # 1. Load ALL historical data to ensure correct YoY/YTD calculations
        historical_df = load_historical_data()
        if historical_df.empty:
            print("No data found. Exiting.")
            return

        # 2. Identify the last month from the datetime of the system and gets the last day of that month
        latest_date = pd.to_datetime("today").replace(day=1) - pd.DateOffset(days=1)

        print(f"Identified the last month as: {latest_date.strftime('%B %Y')}")

        # 3. Calculate advanced metrics for the ENTIRE dataset
        final_metrics_df = calculate_advanced_metrics(historical_df)
        
        # 4. Filter the results to include ONLY the last month data
        # The 'Date' column in final_metrics_df is a string 'YYYY-MM-DD', so we format for comparison
        latest_date_str = latest_date.strftime('%Y-%m-%d')
        last_month_df = final_metrics_df[final_metrics_df['Date'] == latest_date_str].copy()
        print(f"Filtering data to upload only for {latest_date_str}.")
        
        # 5. Update the Google Sheet with just the filtered, last-month data
        update_google_sheet(last_month_df, sheet_name="Analytics")
        
        print("✨ Process complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process and update Google Sheets with metrics')
    parser.add_argument('--mode', 
                       choices=['historical', 'current'], 
                       default='historical',
                       help='Mode: "historical" for finalized monthly data, "current" for current month progress')
    
    args = parser.parse_args()
    main(mode=args.mode)