import os
import datetime
import dotenv
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

dotenv.load_dotenv()

CONFIG = {
    "SPREADSHEET_ID": os.getenv("GOOGLE_SHEET_ID"),
    "TAB_ANALYTICS": "Analytics",
    "TAB_CURRENT": "Current Month",
    "DATE_MODE": "auto", 
    "MANUAL_TARGET_MONTH": "2025-12",
}

METRICS_MAP = {
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

class SheetsUpdater:
    def __init__(self):
        user = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASSWORD", "")
        host = os.getenv("DB_HOST", "localhost")
        db_name = os.getenv("DB_NAME", "tu_base_de_datos")
        
        self.db_engine = create_engine(f'mysql+mysqlconnector://{user}:{password}@{host}/{db_name}')
        self.sheets_client = self._init_sheets_client()

    def _init_sheets_client(self):
        path = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")
        if not path: raise ValueError("❌ Falta GOOGLE_SHEETS_CREDENTIALS_PATH")
        creds = service_account.Credentials.from_service_account_file(
            path, scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        return build('sheets', 'v4', credentials=creds)

    def get_db_data(self):
        print("📥 Descargando histórico desde SQL...")
        query = "SELECT fecha, metrica, valor FROM comunicacion ORDER BY fecha ASC"
        
        try:
            with self.db_engine.connect() as conn:
                df = pd.read_sql(query, conn)
            
            if df.empty:
                print("⚠️ La base de datos está vacía.")
                return pd.DataFrame()

            df.columns = ['Date', 'Metric', 'Value']
            df['Date'] = pd.to_datetime(df['Date'])
            df['Metric'] = df['Metric'].map(METRICS_MAP)
            df.dropna(subset=['Metric'], inplace=True)
            return df
        except Exception as e:
            print(f"🔥 Error de Base de Datos: {e}")
            return pd.DataFrame()

    def calculate_metrics(self, df):
        if df.empty: return df
        print("🧮 Calculando métricas avanzadas (YTD, YoY, Previous FY)...")
        df = df.sort_values(by=['Metric', 'Date'])
        
        # 1. Año Fiscal (Agosto a Julio)
        df['fiscal_group'] = np.where(df['Date'].dt.month >= 8, df['Date'].dt.year, df['Date'].dt.year - 1)
        
        # 2. YTD (Corregido para manejar Promedios Acumulados)
        # Calculamos la suma acumulada y el número de meses transcurridos en el año fiscal
        df['ytd_sum'] = df.groupby(['Metric', 'fiscal_group'])['Value'].cumsum()
        df['cum_count'] = df.groupby(['Metric', 'fiscal_group']).cumcount() + 1
        df['ytd_mean'] = df['ytd_sum'] / df['cum_count']
        
        # Si la métrica es "Views Per Session", usamos la media acumulada; si no, la suma
        df['ytd'] = np.where(
            df['Metric'].str.contains('Views Per Session'),
            df['ytd_mean'],
            df['ytd_sum']
        )
        df['ytd'] = df['ytd'].round(2) # Redondear YTD a 2 decimales
        df.drop(columns=['ytd_sum', 'cum_count', 'ytd_mean'], inplace=True)

        # 3. YoY
        df['Date_Target'] = df['Date'] + pd.DateOffset(years=1)
        df_shifted = df[['Date', 'Metric', 'Value', 'ytd']].copy()
        df_shifted.rename(columns={'Date': 'Date_Prev'}, inplace=True) 
        df['Date_Last_Year'] = df['Date'] - pd.DateOffset(years=1)
        
        df_final = pd.merge(
            df,
            df_shifted[['Date_Prev', 'Metric', 'Value', 'ytd']],
            left_on=['Date_Last_Year', 'Metric'],
            right_on=['Date_Prev', 'Metric'],
            how='left',
            suffixes=('', '_prev')
        )
        
        df_final.rename(columns={'Value_prev': 'year_over_year', 'ytd_prev': 'ytd_over_year'}, inplace=True)
        df_final['ytd_over_year'] = df_final['ytd_over_year'].round(2) # Redondear YoY de YTD

        # 4. Cálculo del Año Fiscal Anterior Completo
        fy_agg = df.groupby(['fiscal_group', 'Metric'])['Value'].agg(['sum', 'mean']).reset_index()
        
        fy_agg['Previous_FY_Value'] = np.where(
            fy_agg['Metric'].str.contains('Views Per Session'), 
            fy_agg['mean'], 
            fy_agg['sum']
        )
        fy_agg['Previous_FY_Value'] = fy_agg['Previous_FY_Value'].round(2) # Redondear FY Previo
        
        fy_agg['fiscal_group'] = fy_agg['fiscal_group'] + 1
        
        df_final = pd.merge(
            df_final,
            fy_agg[['fiscal_group', 'Metric', 'Previous_FY_Value']],
            on=['fiscal_group', 'Metric'],
            how='left'
        )

        cols = ['Date', 'Metric', 'Value', 'ytd', 'year_over_year', 'ytd_over_year', 'Previous_FY_Value']
        return df_final[cols].fillna(0)

    def upload_to_sheet(self, df, sheet_name):
        if df.empty:
            print(f"⚠️ No hay datos para subir a {sheet_name}.")
            return
        
        df_upload = df.copy()
        df_upload['Date'] = df_upload['Date'].dt.strftime('%Y-%m-%d')
        df_upload = df_upload.fillna(0)
        values = [df_upload.columns.tolist()] + df_upload.values.tolist()
        body = {'values': values}
        
        try:
            print(f"☁️ Subiendo {len(df_upload)} filas a '{sheet_name}'...")
            self.sheets_client.spreadsheets().values().clear(
                spreadsheetId=CONFIG["SPREADSHEET_ID"], range=sheet_name
            ).execute()
            self.sheets_client.spreadsheets().values().update(
                spreadsheetId=CONFIG["SPREADSHEET_ID"], range=f"{sheet_name}!A1",
                valueInputOption="USER_ENTERED", body=body
            ).execute()
            print(f"✅ {sheet_name} actualizada.")
        except HttpError as e:
            print(f"❌ Error API Google: {e}")

    def run(self):
        today = datetime.date.today()
        
        if CONFIG["DATE_MODE"] == "manual":
            target_y, target_m = map(int, CONFIG["MANUAL_TARGET_MONTH"].split('-'))
            prev_month_date = datetime.date(target_y, target_m, 1)
            current_month_date = today.replace(day=1)
        else:
            current_month_date = today.replace(day=1)
            first = today.replace(day=1)
            prev_month_date = (first - datetime.timedelta(days=1)).replace(day=1)

        print(f"🎯 Configuración: Analytics={prev_month_date.strftime('%Y-%m')} | Current={current_month_date.strftime('%Y-%m')}")

        full_data = self.get_db_data()
        processed_data = self.calculate_metrics(full_data)

        if processed_data.empty:
            print("❌ No se pudo procesar la información.")
            return

        # Filtrar Analytics (Mes cerrado)
        analytics_df = processed_data[
            (processed_data['Date'].dt.year == prev_month_date.year) & 
            (processed_data['Date'].dt.month == prev_month_date.month)
        ].copy()
        self.upload_to_sheet(analytics_df, CONFIG["TAB_ANALYTICS"])

        # Filtrar Current Month (Mes actual)
        current_df = processed_data[
            (processed_data['Date'].dt.year == current_month_date.year) & 
            (processed_data['Date'].dt.month == current_month_date.month)
        ].copy()
        
        cols_current = ['Date', 'Metric', 'Value', 'Previous_FY_Value'] 
        self.upload_to_sheet(current_df[cols_current], CONFIG["TAB_CURRENT"])

if __name__ == "__main__":
    updater = SheetsUpdater()
    updater.run()