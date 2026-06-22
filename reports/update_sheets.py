import os
import datetime
import pandas as pd
import numpy as np

import sys
import os

# Agrega la carpeta raíz del proyecto a las rutas del sistema para que encuentre 'config' y 'db'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importaciones centralizadas
from config.settings import CONFIG
from db.database import get_sqlalchemy_engine

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

REPORT_CONFIG = {
    "TAB_ANALYTICS": "Analytics",
    "TAB_CURRENT": "Current Month",
    "DATE_MODE": "auto", 
    "MANUAL_TARGET_MONTH": "2025-12",
}

class SheetsUpdater:
    def __init__(self):
        self.db_engine = get_sqlalchemy_engine()
        self.sheets_client = self._init_sheets_client()

    def _init_sheets_client(self):
        path = CONFIG.get("GA4_CREDENTIALS")  # Asumiendo que usas la misma Service Account para Sheets
        if not path: raise ValueError("❌ Falta GA4_CREDENTIALS_PATH en .env para autenticar Sheets")
        creds = service_account.Credentials.from_service_account_file(
            path, scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        return build('sheets', 'v4', credentials=creds)

    def get_db_data(self):
        if not self.db_engine:
            return pd.DataFrame()
            
        print("📥 Descargando histórico consolidado de MySQL...")
        query = """
            SELECT c.fecha AS Date, g.nombre AS Metric, c.valor AS Value 
            FROM comunicacion c
            JOIN glosario_comunicacion g ON c.metrica = g.metrica
            ORDER BY c.fecha ASC
        """
        
        try:
            with self.db_engine.connect() as conn:
                df = pd.read_sql(query, conn)
            
            if df.empty:
                print("⚠️ La base de datos está vacía.")
                return pd.DataFrame()

            df['Date'] = pd.to_datetime(df['Date'])
            df.dropna(subset=['Metric'], inplace=True)
            return df
        except Exception as e:
            print(f"🔥 Error de Base de Datos: {e}")
            return pd.DataFrame()

    def calculate_metrics(self, df):
        if df.empty: return df
        print("🧮 Calculando métricas avanzadas (YTD, YoY, Previous FY)...")
        df = df.sort_values(by=['Metric', 'Date'])
        
        # 1. Definir Año Fiscal Actual (Ej. Mar 2026 -> 2025, Ago 2024 -> 2024)
        df['fiscal_year'] = np.where(df['Date'].dt.month >= 8, df['Date'].dt.year, df['Date'].dt.year - 1)
        
        # --- Cálculo de YTD ---
        df['ytd_sum'] = df.groupby(['Metric', 'fiscal_year'])['Value'].cumsum()
        df['cum_count'] = df.groupby(['Metric', 'fiscal_year']).cumcount() + 1
        df['ytd_mean'] = df['ytd_sum'] / df['cum_count']
        
        df['ytd'] = np.where(
            df['Metric'].str.contains('Session'),
            df['ytd_mean'],
            df['ytd_sum']
        )
        df['ytd'] = df['ytd'].round(2)
        df.drop(columns=['ytd_sum', 'cum_count', 'ytd_mean'], inplace=True)

        # --- Cálculo de YoY ---
        df['Month'] = df['Date'].dt.month
        df['Year_Last'] = df['Date'].dt.year - 1
        
        df_shifted = df[['Date', 'Metric', 'Value', 'ytd']].copy()
        df_shifted['Month_prev'] = df_shifted['Date'].dt.month
        df_shifted['Year_prev'] = df_shifted['Date'].dt.year
        df_shifted.rename(columns={'Value': 'year_over_year', 'ytd': 'ytd_over_year'}, inplace=True)
        
        df_final = pd.merge(
            df,
            df_shifted[['Metric', 'Month_prev', 'Year_prev', 'year_over_year', 'ytd_over_year']],
            left_on=['Metric', 'Month', 'Year_Last'],
            right_on=['Metric', 'Month_prev', 'Year_prev'],
            how='left'
        )
        df_final['year_over_year'] = df_final['year_over_year'].fillna(0)
        df_final['ytd_over_year'] = df_final['ytd_over_year'].fillna(0).round(2)

        # --- Cálculo de Previous FY ---
        df_final['prev_fiscal_year'] = df_final['fiscal_year'] - 1
        
        fy_agg = df_final.groupby(['fiscal_year', 'Metric'])['Value'].agg(['sum', 'mean']).reset_index()
        
        fy_agg['Previous_FY_Value'] = np.where(
            fy_agg['Metric'].str.contains('Session'), 
            fy_agg['mean'], 
            fy_agg['sum']
        )
        fy_agg['Previous_FY_Value'] = fy_agg['Previous_FY_Value'].round(2)
        
        df_final = pd.merge(
            df_final,
            fy_agg[['fiscal_year', 'Metric', 'Previous_FY_Value']],
            left_on=['prev_fiscal_year', 'Metric'],
            right_on=['fiscal_year', 'Metric'],
            how='left',
            suffixes=('', '_agg')
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
                spreadsheetId=CONFIG["GOOGLE_SHEET_ID"], range=sheet_name
            ).execute()
            self.sheets_client.spreadsheets().values().update(
                spreadsheetId=CONFIG["GOOGLE_SHEET_ID"], range=f"{sheet_name}!A1",
                valueInputOption="USER_ENTERED", body=body
            ).execute()
            print(f"✅ {sheet_name} actualizada correctamente.")
        except HttpError as e:
            print(f"❌ Error API Google: {e}")

    def run(self):
        today = datetime.date.today()
        
        if REPORT_CONFIG["DATE_MODE"] == "manual":
            target_y, target_m = map(int, REPORT_CONFIG["MANUAL_TARGET_MONTH"].split('-'))
            prev_month_date = datetime.date(target_y, target_m, 1)
            current_month_date = today.replace(day=1)
        else:
            current_month_date = today.replace(day=1)
            first = today.replace(day=1)
            prev_month_date = (first - datetime.timedelta(days=1)).replace(day=1)

        print(f"🎯 Configuración: Analytics={prev_month_date.strftime('%Y-%m')} | Current={current_month_date.strftime('%Y-%m')}")

        full_data = self.get_db_data()
        processed_data = self.calculate_metrics(full_data)

        if processed_data.empty: return

        # Filtrar datos del mes histórico (Analytics)
        analytics_df = processed_data[
            (processed_data['Date'].dt.year == prev_month_date.year) & 
            (processed_data['Date'].dt.month == prev_month_date.month)
        ].copy()
        self.upload_to_sheet(analytics_df, REPORT_CONFIG["TAB_ANALYTICS"])

        # Filtrar datos del mes en curso (Current Month)
        current_df = processed_data[
            (processed_data['Date'].dt.year == current_month_date.year) & 
            (processed_data['Date'].dt.month == current_month_date.month)
        ].copy()
        
        cols_current = ['Date', 'Metric', 'Value', 'Previous_FY_Value'] 
        self.upload_to_sheet(current_df[cols_current], REPORT_CONFIG["TAB_CURRENT"])

if __name__ == "__main__":
    updater = SheetsUpdater()
    updater.run()