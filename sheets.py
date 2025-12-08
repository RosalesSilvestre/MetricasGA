import os
import glob
import pandas as pd
import numpy as np
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

def calculate_advanced_metrics(df):
    """
    Calculates YTD and YoY metrics, applying SUM for most metrics and 
    AVERAGE for session-based metrics, based on a fiscal year starting in August.
    """
    if df.empty:
        return df

    # --- Lógica de Año Fiscal (sin cambios) ---
    df['fiscal_year'] = np.where(df['Date'].dt.month >= 8, 
                                df['Date'].dt.year, 
                                df['Date'].dt.year - 1)

    # --- CAMBIO CLAVE: Lógica de Agregación Diferenciada ---

    # 1. Definir qué métricas se promedian en lugar de sumarse
    metrics_to_average = [
        "ITAM Views Per Session",
        "Blog Views Per Session",
        "Carreras Views Per Session"
    ]

    # 2. Separar el DataFrame en dos, según la lógica de agregación
    df_sum = df[~df['Metric'].isin(metrics_to_average)].copy()
    df_avg = df[df['Metric'].isin(metrics_to_average)].copy()

    # 3. Calcular YTD para las métricas que se SUMAN (lógica anterior)
    if not df_sum.empty:
        df_sum['ytd'] = df_sum.groupby(['Metric', 'fiscal_year'])['Value'].cumsum()

    # 4. Calcular YTD para las métricas que se PROMEDIAN
    if not df_avg.empty:
        # .expanding().mean() calcula el promedio de todos los valores desde el inicio del grupo
        # hasta la fila actual, lo que es un "promedio acumulado".
        ytd_avg = df_avg.groupby(['Metric', 'fiscal_year'])['Value'].expanding().mean()
        # El resultado de expanding tiene un multi-índice, lo reseteamos para que coincida
        df_avg['ytd'] = ytd_avg.reset_index(level=[0,1], drop=True)

    # 5. Unir los DataFrames y ordenar para asegurar la consistencia antes de los cálculos YoY
    df_final = pd.concat([df_sum, df_avg])
    df_final.sort_values(by=['Metric', 'Date'], inplace=True)

    # 6. Calcular métricas YoY sobre el DF completo y ordenado
    df_final['year_over_year'] = df_final.groupby('Metric')['Value'].shift(12)
    df_final['ytd_over_year'] = df_final.groupby('Metric')['ytd'].shift(12)

    # --- Formato de salida (sin cambios) ---
    final_df_formatted = df_final[[
        'Date', 'Metric', 'Value', 'ytd', 'year_over_year', 'ytd_over_year'
    ]].copy()
    
    final_df_formatted['Date'] = final_df_formatted['Date'].dt.strftime('%Y-%m-%d')
    
    return final_df_formatted


def update_google_sheet(df):
    """
    Clears and updates a Google Sheet with the final calculated data.
    """
    if df.empty:
        print("Dataframe is empty, skipping Google Sheet update.")
        return
        
    try:
        GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
        GOOGLE_SHEETS_CREDENTIALS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")
        SHEET_NAME = "Analytics"  # Or the name of the sheet you want to update

        if not all([GOOGLE_SHEET_ID, GOOGLE_SHEETS_CREDENTIALS_PATH]):
            raise ValueError("Google Sheet environment variables are not set.")

        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_SHEETS_CREDENTIALS_PATH,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()

        df.fillna('', inplace=True)
        values_to_upload = [df.columns.tolist()] + df.values.tolist()

        print(f"Clearing existing data from sheet: '{SHEET_NAME}'...")
        sheet.values().clear(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=SHEET_NAME
        ).execute()

        print(f"Writing {len(df)} rows of new data to the sheet...")
        body = {'values': values_to_upload}
        result = sheet.values().update(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        
        print(f"✅ Success! {result.get('updatedCells')} cells updated in Google Sheet '{SHEET_NAME}'.")

    except HttpError as err:
        print(f"❌ An API error occurred: {err}")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")

def main():
    """
    Main execution function to orchestrate data loading, calculation,
    and updating the sheet with the LATEST month's data only.
    """
    print("🚀 Starting metrics aggregation process...")
    
    historical_df = load_historical_data()
    if historical_df.empty:
        print("No data found. Exiting.")
        return

    latest_date = pd.to_datetime("today").replace(day=1) - pd.DateOffset(days=1)
    print(f"Identified the last month as: {latest_date.strftime('%B %Y')}")

    final_metrics_df = calculate_advanced_metrics(historical_df)
    
    latest_date_str = latest_date.strftime('%Y-%m-%d')
    last_month_df = final_metrics_df[final_metrics_df['Date'] == latest_date_str].copy()
    print(f"Filtering data to upload only for {latest_date_str}.")
    
    update_google_sheet(last_month_df)
    
    print("✨ Process complete.")

if __name__ == "__main__":
    main()