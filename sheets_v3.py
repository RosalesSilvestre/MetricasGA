import os
import datetime
import dotenv
import pandas as pd
import numpy as np
import mysql.connector
from mysql.connector import Error

# Google Libraries
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

dotenv.load_dotenv()

# ==========================================
#      ZONA DE CONFIGURACIÓN (EDITAR AQUÍ)
# ==========================================

CONFIG = {
    # ID de la Hoja de Cálculo de Google (Test metricas)
    "SPREADSHEET_ID": os.getenv("GOOGLE_SHEET_ID", "TU_ID_DE_SHEET_AQUI"),
    
    # Nombres de las pestañas en el Google Sheet
    "TAB_ANALYTICS": "Analytics",       # Para el mes cerrado
    "TAB_CURRENT": "Current Month",     # Para el mes en curso

    # MODO DE FECHA:
    # 'auto'   -> Calcula automáticamente el mes anterior y el actual.
    # 'manual' -> Usa las fechas definidas abajo en 'MANUAL_TARGET'.
    "DATE_MODE": "auto",

    # SOLO SI DATE_MODE es 'manual' (Formato YYYY-MM)
    "MANUAL_TARGET_MONTH": "2024-12",  # Mes que irá a la pestaña 'Analytics'
}

# ==========================================
#          FIN DE CONFIGURACIÓN
# ==========================================

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
        self.db_config = {
            'host': os.getenv("DB_HOST", "localhost"),
            'database': os.getenv("DB_NAME", "tu_base_de_datos"),
            'user': os.getenv("DB_USER", "root"),
            'password': os.getenv("DB_PASSWORD", ""),
        }
        self.sheets_client = self._init_sheets_client()

    def _init_sheets_client(self):
        """Inicializa el cliente de Google Sheets."""
        path = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")
        if not path:
            raise ValueError("❌ Falta GOOGLE_SHEETS_CREDENTIALS_PATH en .env")
        
        creds = service_account.Credentials.from_service_account_file(
            path, scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        return build('sheets', 'v4', credentials=creds)

    def get_db_data(self):
        """Extrae TODO el histórico de la BD para poder calcular YTD y YoY correctamente."""
        print("📥 Descargando histórico desde SQL...")
        try:
            conn = mysql.connector.connect(**self.db_config)
            query = "SELECT fecha, metrica, valor FROM comunicacion ORDER BY fecha ASC"
            df = pd.read_sql(query, conn)
            conn.close()
            
            if df.empty:
                print("⚠️ La base de datos está vacía.")
                return pd.DataFrame()

            # Renombrar y formatear
            df.columns = ['Date', 'Metric', 'Value']
            df['Date'] = pd.to_datetime(df['Date'])
            df['Metric'] = df['Metric'].map(METRICS_MAP)
            df.dropna(subset=['Metric'], inplace=True)
            
            return df
        except Error as e:
            print(f"🔥 Error de Base de Datos: {e}")
            return pd.DataFrame()

    def calculate_metrics(self, df):
        """Aplica la lógica de negocio: Año Fiscal (Agosto), YTD, YoY."""
        if df.empty: return df
        
        print("🧮 Calculando métricas avanzadas (YTD, YoY)...")
        df = df.sort_values(by=['Metric', 'Date'])

        # 1. Definir Año Fiscal (Empieza en Agosto)
        # Si mes >= 8, pertenece al año fiscal del año actual. Si no, al anterior.
        # Ejemplo: Ago 2023 es FY2023. Ene 2024 sigue siendo FY2023 (en lógica de ciclo escolar/fiscal).
        # Nota: Ajusta esta lógica si tu año fiscal se llama "2024" empezando en Ago 2023.
        # Aquí usaremos un identificador único para agrupar el acumulado.
        df['fiscal_group'] = np.where(df['Date'].dt.month >= 8, 
                                      df['Date'].dt.year, 
                                      df['Date'].dt.year - 1)

        # 2. Calcular YTD (Year to Date) reiniciando en Agosto
        df['ytd'] = df.groupby(['Metric', 'fiscal_group'])['Value'].cumsum()

        # 3. Calcular YoY (Year over Year) - Comparado con el mismo mes del año anterior
        # Shift de 12 periodos asumiendo que hay datos mensuales continuos. 
        # Para ser más robusto, hacemos un merge con sigo mismo desfasado 1 año.
        df['month_id'] = df['Date'].dt.month
        
        # Self-join para encontrar el valor exacto de hace 1 año
        df_shifted = df[['Date', 'Metric', 'Value', 'ytd']].copy()
        df_shifted['Date_Target'] = df_shifted['Date'] + pd.DateOffset(years=1)
        
        # Hacemos merge donde Date del original coincida con Date_Target del shifted
        # Esto trae los valores de "hace un año" a la fila actual
        df_final = pd.merge(
            df, 
            df_shifted[['Date_Target', 'Metric', 'Value', 'ytd']], 
            left_on=['Date', 'Metric'], 
            right_on=['Date_Target', 'Metric'], 
            how='left', 
            suffixes=('', '_prev')
        )
        
        df_final.rename(columns={
            'Value_prev': 'year_over_year',
            'ytd_prev': 'ytd_over_year'
        }, inplace=True)

        # Limpieza final
        cols = ['Date', 'Metric', 'Value', 'ytd', 'year_over_year', 'ytd_over_year']
        return df_final[cols].fillna(0)

    def upload_to_sheet(self, df, sheet_name):
        """Sube un DataFrame a una pestaña específica, borrando lo anterior."""
        if df.empty:
            print(f"⚠️ No hay datos para subir a {sheet_name}.")
            return

        # Preparar datos para API (convertir a lista de listas y strings)
        df_upload = df.copy()
        df_upload['Date'] = df_upload['Date'].dt.strftime('%Y-%m-%d')
        df_upload = df_upload.fillna(0)
        
        values = [df_upload.columns.tolist()] + df_upload.values.tolist()
        
        body = {'values': values}
        
        try:
            print(f"☁️ Subiendo {len(df_upload)} filas a '{sheet_name}'...")
            
            # 1. Limpiar hoja
            self.sheets_client.spreadsheets().values().clear(
                spreadsheetId=CONFIG["SPREADSHEET_ID"],
                range=sheet_name
            ).execute()
            
            # 2. Escribir nuevos datos
            self.sheets_client.spreadsheets().values().update(
                spreadsheetId=CONFIG["SPREADSHEET_ID"],
                range=f"{sheet_name}!A1",
                valueInputOption="USER_ENTERED",
                body=body
            ).execute()
            print(f"✅ {sheet_name} actualizada exitosamente.")
            
        except HttpError as e:
            print(f"❌ Error al subir a Google Sheets: {e}")

    def run(self):
        # 1. Obtener Fechas Objetivo
        today = datetime.date.today()
        
        if CONFIG["DATE_MODE"] == "manual":
            # Modo Manual
            target_y, target_m = map(int, CONFIG["MANUAL_TARGET_MONTH"].split('-'))
            prev_month_date = datetime.date(target_y, target_m, 1)
            # Para current month en manual, usamos "hoy" o definimos otra lógica, 
            # pero por defecto dejaremos el mes actual real del sistema.
            current_month_date = today.replace(day=1)
        else:
            # Modo Automático
            current_month_date = today.replace(day=1)
            first = today.replace(day=1)
            prev_month_date = first - datetime.timedelta(days=1)
            prev_month_date = prev_month_date.replace(day=1)

        print(f"🎯 Configuración: \n   - Mes Cerrado (Analytics): {prev_month_date.strftime('%Y-%m')}\n   - Mes En Curso (Current): {current_month_date.strftime('%Y-%m')}")

        # 2. Obtener y Procesar Datos
        full_data = self.get_db_data()
        processed_data = self.calculate_metrics(full_data)

        if processed_data.empty:
            print("❌ No se pudo procesar la información.")
            return

        # 3. Filtrar y Subir 'Analytics' (Mes Anterior Completo)
        # Filtramos para obtener todas las filas que caigan en el mes/año del target
        analytics_df = processed_data[
            (processed_data['Date'].dt.year == prev_month_date.year) & 
            (processed_data['Date'].dt.month == prev_month_date.month)
        ].copy()
        
        self.upload_to_sheet(analytics_df, CONFIG["TAB_ANALYTICS"])

        # 4. Filtrar y Subir 'Current Month' (Lo que va del mes actual)
        # Para el mes actual, a veces solo queremos metricas crudas, pero si quieres YTD también, usa processed_data.
        # Según tu Excel de ejemplo 'Current Month' solo tenía Date, Metric, Value.
        current_df = processed_data[
            (processed_data['Date'].dt.year == current_month_date.year) & 
            (processed_data['Date'].dt.month == current_month_date.month)
        ].copy()
        
        # Seleccionamos solo las columnas básicas para Current Month (según tu ejemplo)
        # Si quieres ver YTD también aquí, agrega las columnas a la lista.
        cols_current = ['Date', 'Metric', 'Value'] 
        self.upload_to_sheet(current_df[cols_current], CONFIG["TAB_CURRENT"])

if __name__ == "__main__":
    updater = SheetsUpdater()
    updater.run()