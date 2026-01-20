import os
import datetime
import dotenv
import mysql.connector
from mysql.connector import Error

# Google Libraries
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange, Metric, RunReportRequest, Filter, FilterExpression
)
from googleapiclient.discovery import build

dotenv.load_dotenv()

# ==========================================
#      ZONA DE CONFIGURACIÓN (EDITAR AQUÍ)
# ==========================================

CONFIG = {
    # MODOS DISPONIBLES:
    # 'month'      -> Procesa un solo mes.
    # 'soft_reset' -> Recorre el histórico e inserta SOLO lo que falte (rápido).
    # 'hard_reset' -> Borra y reescribe el histórico completo (lento, borra datos previos).
    "MODE": "soft_reset", 

    # CONFIGURACIÓN PARA MODO 'month':
    # 'YYYY-MM' -> Para procesar un mes específico (ej: '2024-01').
    # None      -> Para procesar automáticamente el mes anterior al actual.
    "TARGET_MONTH": None, 

    # CONFIGURACIÓN PARA MODO HISTÓRICO ('soft_reset' o 'hard_reset'):
    # Año desde el cual empezar a verificar/reconstruir.
    "START_YEAR": 2023 
}

# ==========================================
#          FIN DE CONFIGURACIÓN
# ==========================================

# Mapeo de IDs de Base de Datos
METRICS_MAP = {
    "itam.mx":          {"totalUsers": 1, "views": 2, "viewsPerSession": 3},
    "blog.itam.mx":     {"totalUsers": 4, "views": 5, "viewsPerSession": 6},
    "carreras.itam.mx": {"totalUsers": 7, "views": 8, "viewsPerSession": 9},
    "youtube":          {"ads": 10, "organic": 11, "total": 12}
}

FECHA_CAMBIO_GA4 = '2024-10-01'

class MetricsETL:
    def __init__(self):
        self.db_config = {
            'host': os.getenv("DB_HOST", "localhost"),
            'database': os.getenv("DB_NAME", "tu_base_de_datos"),
            'user': os.getenv("DB_USER", "root"),
            'password': os.getenv("DB_PASSWORD", ""),
        }
        self.ga4_client = self._init_ga4_client()
        self.yt_client = self._init_yt_client()

    def _init_ga4_client(self):
        path = os.getenv("GA4_CREDENTIALS_PATH")
        if not path: raise ValueError("Falta GA4_CREDENTIALS_PATH en .env")
        creds = service_account.Credentials.from_service_account_file(
            path, scopes=["https://www.googleapis.com/auth/analytics.readonly"]
        )
        return BetaAnalyticsDataClient(credentials=creds)

    def _init_yt_client(self):
        token_path = os.getenv("TOKEN_FILE")
        if not token_path or not os.path.exists(token_path):
            print("⚠️  Advertencia: No se encontró token de YouTube. Las métricas de YT serán 0.")
            return None
        creds = Credentials.from_authorized_user_file(
            token_path, ["https://www.googleapis.com/auth/yt-analytics.readonly"]
        )
        return build("youtubeAnalytics", "v2", credentials=creds)

    def get_date_range(self, year, month):
        start_date = datetime.date(year, month, 1)
        if month == 12:
            end_date = datetime.date(year, 12, 31)
        else:
            end_date = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    def fetch_ga4(self, start_date, end_date):
        data_points = []
        
        properties_config = {
            'itam.mx': {'id': os.getenv("ITAM_GA4_PROPERTY_ID"), 'filter': None},
            'blog.itam.mx': {'id': os.getenv("ITAM_BLOG_GA4_PROPERTY_ID"), 'filter': None}
        }

        # Lógica de cambio de propiedad Carreras
        if start_date >= FECHA_CAMBIO_GA4:
            properties_config['carreras.itam.mx'] = {
                'id': os.getenv("ITAM_CARRERAS_GA4_PROPERTY_ID_NEW"),
                'filter': None
            }
        else:
            filtr = FilterExpression(
                filter=Filter(field_name="hostName", string_filter=Filter.StringFilter(value="aspirantes.itam.mx"))
            )
            properties_config['carreras.itam.mx'] = {
                'id': os.getenv("ITAM_CARRERAS_GA4_PROPERTY_ID_OLD"),
                'filter': filtr
            }

        for name, config in properties_config.items():
            if not config['id']: continue
            
            req = RunReportRequest(
                property=f"properties/{config['id']}",
                metrics=[Metric(name="totalUsers"), Metric(name="screenPageViews"), Metric(name="screenPageViewsPerSession")],
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimension_filter=config['filter']
            )

            try:
                resp = self.ga4_client.run_report(req)
                if resp.rows:
                    row = resp.rows[0]
                    vals = {
                        "totalUsers": int(row.metric_values[0].value),
                        "views": int(row.metric_values[1].value),
                        "viewsPerSession": round(float(row.metric_values[2].value), 2)
                    }
                    for key, val in vals.items():
                        metric_id = METRICS_MAP[name][key]
                        data_points.append((end_date, metric_id, val))
            except Exception as e:
                print(f"❌ Error GA4 en {name}: {e}")
        
        return data_points

    def fetch_youtube(self, start_date, end_date):
        data_points = []
        if not self.yt_client: return []

        try:
            resp = self.yt_client.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="views",
                dimensions="insightTrafficSourceType"
            ).execute()

            ad_views = 0
            total_views = 0

            if "rows" in resp:
                for row in resp["rows"]:
                    source, views = row[0], int(row[1])
                    total_views += views
                    if source == 'ADVERTISING':
                        ad_views += views
            
            organic_views = total_views - ad_views

            data_points.append((end_date, METRICS_MAP['youtube']['ads'], ad_views))
            data_points.append((end_date, METRICS_MAP['youtube']['organic'], organic_views))
            data_points.append((end_date, METRICS_MAP['youtube']['total'], total_views))

        except Exception as e:
            print(f"❌ Error YouTube: {e}")
        
        return data_points

    def save_to_db(self, data, mode='soft'):
        if not data:
            print("⚠️  No hay datos para guardar.")
            return

        # soft = INSERT IGNORE (solo llena huecos)
        # hard = REPLACE INTO (sobrescribe todo)
        query_type = "INSERT IGNORE" if mode == 'soft' else "REPLACE"
        sql = f"{query_type} INTO comunicacion (fecha, metrica, valor) VALUES (%s, %s, %s)"

        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            cursor.executemany(sql, data)
            conn.commit()
            print(f"✅ DB: {cursor.rowcount} registros procesados ({mode}).")

        except Error as e:
            print(f"🔥 Error de Base de Datos: {e}")
        finally:
            if 'conn' in locals() and conn.is_connected():
                cursor.close()
                conn.close()

    def process_month(self, year, month, mode):
        start, end = self.get_date_range(year, month)
        print(f"🔄 Procesando periodo: {start} al {end} ...")
        
        ga_data = self.fetch_ga4(start, end)
        yt_data = self.fetch_youtube(start, end)
        
        full_data = ga_data + yt_data
        self.save_to_db(full_data, mode)

    def run_historical(self, start_year, mode):
        today = datetime.date.today()
        print(f"🚀 Iniciando carga histórica desde {start_year} (Modo: {mode})")
        
        for year in range(start_year, today.year + 1):
            start_month = 1
            end_month = 12
            
            if year == today.year:
                end_month = today.month - 1 
            
            # Si estamos en enero, el loop anterior no corre para el año actual, ajustamos
            if end_month < 1: 
                continue

            for month in range(start_month, end_month + 1):
                self.process_month(year, month, mode)

# ==========================================
#           EJECUCIÓN PRINCIPAL
# ==========================================

if __name__ == "__main__":
    etl = MetricsETL()
    mode = CONFIG["MODE"]

    if mode == 'month':
        target = CONFIG["TARGET_MONTH"]
        
        if target:
            # Caso 1: Mes específico definido por usuario
            year, month = map(int, target.split('-'))
            print(f"📅 Modo Mensual Manual: {target}")
            etl.process_month(year, month, mode='hard') # Siempre hard para actualizaciones manuales
            
        else:
            # Caso 2: Automático (Mes anterior)
            today = datetime.date.today()
            first_day_this_month = today.replace(day=1)
            prev_month_date = first_day_this_month - datetime.timedelta(days=1)
            
            print(f"📅 Modo Mensual Automático: {prev_month_date.strftime('%Y-%m')}")
            etl.process_month(prev_month_date.year, prev_month_date.month, mode='hard')

    elif mode in ['soft_reset', 'hard_reset']:
        # Caso 3: Cargas históricas
        # soft_reset -> 'soft' para INSERT IGNORE
        # hard_reset -> 'hard' para REPLACE INTO
        db_mode = 'soft' if mode == 'soft_reset' else 'hard'
        etl.run_historical(CONFIG["START_YEAR"], db_mode)

    else:
        print(f"❌ Error: El modo '{mode}' no es válido en la configuración.")