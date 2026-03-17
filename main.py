import os
import datetime
import calendar
import dotenv
import mysql.connector
from mysql.connector import Error

# Google Libraries
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
# IMPORTANTE: Importamos todo el módulo de tipos para evitar errores de importación individual
from google.analytics.data_v1beta import types 
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials # Necesario para YouTube

dotenv.load_dotenv()

# ==========================================
#      CONFIGURACIÓN
# ==========================================

CONFIG = {
    "MODE": "month",
    "TARGET_MONTH": None,
    # Base de Datos
    "DB_HOST": os.getenv("DB_HOST", "localhost"),
    "DB_NAME": os.getenv("DB_NAME", "tu_base_de_datos"),
    "DB_USER": os.getenv("DB_USER", "root"),
    "DB_PASSWORD": os.getenv("DB_PASSWORD", ""),
    
    # Credenciales y Archivos
    "GA4_CREDENTIALS": os.getenv("GA4_CREDENTIALS_PATH"),
    "TOKEN_FILE": os.getenv("TOKEN_FILE"),
    
    # IDs de Propiedades GA4
    "PROP_ITAM": os.getenv("ITAM_GA4_PROPERTY_ID"),
    "PROP_BLOG": os.getenv("ITAM_BLOG_GA4_PROPERTY_ID"),
    "PROP_CARRERAS_NEW": os.getenv("ITAM_CARRERAS_GA4_PROPERTY_ID_NEW"),
    "PROP_CARRERAS_OLD": os.getenv("ITAM_CARRERAS_GA4_PROPERTY_ID_OLD"),
    
    # Fecha de corte para cambio de propiedad
    "FECHA_NUEVA_INSTALACION": '2024-10-01'
}

METRICS_ID_MAP = {
    "itam_users": 1, "itam_views": 2, "itam_views_per_session": 3,
    "blog_users": 4, "blog_views": 5, "blog_views_per_session": 6,
    "carreras_users": 7, "carreras_views": 8, "carreras_views_per_session": 9,
    "youtube_ads": 10, "youtube_organic": 11, "youtube_total": 12
}

class MetricsETL:
    def __init__(self):
        self.conn = self.get_db_connection()
        self.ga4_client = self.init_ga4()
        self.yt_service = self.init_youtube()

    def get_db_connection(self):
        try:
            return mysql.connector.connect(
                host=CONFIG["DB_HOST"],
                database=CONFIG["DB_NAME"],
                user=CONFIG["DB_USER"],
                password=CONFIG["DB_PASSWORD"]
            )
        except Error as e:
            print(f"❌ Error conectando a MySQL: {e}")
            return None

    def init_ga4(self):
        if not CONFIG["GA4_CREDENTIALS"]:
            print("⚠️ Faltan credenciales GA4 en .env")
            return None
        creds = service_account.Credentials.from_service_account_file(
            CONFIG["GA4_CREDENTIALS"],
            scopes=["https://www.googleapis.com/auth/analytics.readonly"]
        )
        return BetaAnalyticsDataClient(credentials=creds)

    def init_youtube(self):
        if not CONFIG["TOKEN_FILE"] or not os.path.exists(CONFIG["TOKEN_FILE"]):
            print("⚠️ No se encontró TOKEN_FILE para YouTube.")
            return None
        
        creds = Credentials.from_authorized_user_file(
            CONFIG["TOKEN_FILE"], 
            ["https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/yt-analytics.readonly"]
        )
        return build("youtubeAnalytics", "v2", credentials=creds)

    def clean_month_data(self, year, month):
        if not self.conn: return
        cursor = self.conn.cursor()
        query = "DELETE FROM comunicacion WHERE YEAR(fecha) = %s AND MONTH(fecha) = %s"
        try:
            cursor.execute(query, (year, month))
            self.conn.commit()
            print(f"🧹 Datos limpiados en BD para {year}-{month}")
        except Error as err:
            print(f"❌ Error borrando datos: {err}")
        finally:
            cursor.close()

    # ==========================================
    #      LÓGICA DE EXTRACCIÓN (FETCH)
    # ==========================================
    
    def fetch_ga4_single_property(self, property_id, start_date, end_date, dimension_filter=None):
        """Consulta genérica a GA4 para una propiedad dada."""
        if not self.ga4_client or not property_id: return (0, 0, 0.0)

        # Usamos types.X para todo, así evitamos el error de StringFilter
        request = types.RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[types.DateRange(start_date=start_date, end_date=end_date)],
            metrics=[
                types.Metric(name="totalUsers"),
                types.Metric(name="screenPageViews"),
                types.Metric(name="screenPageViewsPerSession")
            ],
            dimension_filter=dimension_filter
        )

        try:
            response = self.ga4_client.run_report(request)
            if not response.rows:
                return (0, 0, 0.0)
            
            row = response.rows[0]
            users = int(row.metric_values[0].value)
            views = int(row.metric_values[1].value)
            vps = round(float(row.metric_values[2].value), 2)
            return (users, views, vps)
            
        except Exception as e:
            print(f"🔥 Error GA4 (Prop ID {property_id}): {e}")
            return (0, 0, 0.0)

    def fetch_all_metrics(self, start_date, end_date):
        print(f"   🔎 Consultando APIs de {start_date} a {end_date}...")

        # 1. ITAM (General)
        itam_u, itam_v, itam_vps = self.fetch_ga4_single_property(CONFIG["PROP_ITAM"], start_date, end_date)
        print(f"      - GA4 ITAM: {itam_v} vistas")

        # 2. BLOG
        blog_u, blog_v, blog_vps = self.fetch_ga4_single_property(CONFIG["PROP_BLOG"], start_date, end_date)
        print(f"      - GA4 Blog: {blog_v} vistas")

        # 3. CARRERAS (Lógica Condicional Nueva vs Vieja)
        carreras_id = None
        carreras_filter = None
        
        # Comparación de strings de fecha YYYY-MM-DD funciona correctamente en Python
        if end_date >= CONFIG["FECHA_NUEVA_INSTALACION"]:
            carreras_id = CONFIG["PROP_CARRERAS_NEW"]
            # print("      (Usando Propiedad Nueva Carreras)")
        else:
            carreras_id = CONFIG["PROP_CARRERAS_OLD"]
            print("      (Usando Propiedad Antigua Carreras con Filtro)")
            
            # Filtro Hostname exacto "aspirantes.itam.mx"
            # SOLUCIÓN DEL ERROR: Usamos types.Filter.StringFilter (Anidado)
            carreras_filter = types.FilterExpression(
                filter=types.Filter(
                    field_name="hostName",
                    string_filter=types.Filter.StringFilter(
                        match_type=types.Filter.StringFilter.MatchType.EXACT,
                        value="aspirantes.itam.mx"
                    )
                )
            )

        carr_u, carr_v, carr_vps = self.fetch_ga4_single_property(carreras_id, start_date, end_date, carreras_filter)
        print(f"      - GA4 Carreras: {carr_v} vistas")

        # 4. YOUTUBE
        yt_ads, yt_org, yt_tot = (0, 0, 0)
        if self.yt_service:
            try:
                response = self.yt_service.reports().query(
                    ids="channel==MINE",
                    startDate=start_date,
                    endDate=end_date,
                    metrics="views",
                    dimensions="insightTrafficSourceType"
                ).execute()
                
                rows = response.get('rows', [])
                for row in rows:
                    source, views = row[0], int(row[1])
                    yt_tot += views
                    if source == 'ADVERTISING':
                        yt_ads += views
                
                yt_org = yt_tot - yt_ads
                print(f"      - YouTube: {yt_tot} vistas ({yt_ads} Ads)")
            except Exception as e:
                print(f"🔥 Error YouTube: {e}")

        return {
            "itam_users": itam_u, "itam_views": itam_v, "itam_views_per_session": itam_vps,
            "blog_users": blog_u, "blog_views": blog_v, "blog_views_per_session": blog_vps,
            "carreras_users": carr_u, "carreras_views": carr_v, "carreras_views_per_session": carr_vps,
            "youtube_ads": yt_ads, "youtube_organic": yt_org, "youtube_total": yt_tot
        }

    def insert_metrics(self, metrics_dict, date_ref):
        if not self.conn: return
        cursor = self.conn.cursor()
        sql = "INSERT INTO comunicacion (fecha, metrica, valor) VALUES (%s, %s, %s)"
        data_to_insert = []
        
        for key, val in metrics_dict.items():
            mid = METRICS_ID_MAP.get(key)
            if mid: data_to_insert.append((date_ref, mid, val))
        
        if data_to_insert:
            try:
                cursor.executemany(sql, data_to_insert)
                self.conn.commit()
                print(f"💾 Guardadas {len(data_to_insert)} métricas en BD para {date_ref}.")
            except Error as e:
                print(f"❌ Error Insert DB: {e}")
        cursor.close()

    def process_month(self, year, month):
        start_date = datetime.date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        
        today = datetime.date.today()
        # Ajuste para mes parcial (Actual) o cerrado
        if start_date.year == today.year and start_date.month == today.month:
            end_date_obj = today 
            print(f"⚠️ Procesando MES ACTUAL (Parcial): {start_date} al {end_date_obj}")
        else:
            end_date_obj = datetime.date(year, month, last_day) 
            print(f"📅 Procesando Mes Cerrado: {start_date} al {end_date_obj}")

        # Limpiar
        self.clean_month_data(year, month)
        
        # Fetch
        s_str = start_date.strftime('%Y-%m-%d')
        e_str = end_date_obj.strftime('%Y-%m-%d')
        metrics = self.fetch_all_metrics(s_str, e_str)
        
        # Insertar
        self.insert_metrics(metrics, end_date_obj)
        print("✅ Listo.\n")

if __name__ == "__main__":
    etl = MetricsETL()
    today = datetime.date.today()
    
    # 1. Mes Anterior
    first = today.replace(day=1)
    prev = first - datetime.timedelta(days=1)
    print(f"--- 1. Ejecutando Mes Anterior ({prev.strftime('%Y-%m')}) ---")
    etl.process_month(prev.year, prev.month)
    
    # 2. Mes Actual
    print(f"--- 2. Ejecutando Mes Actual ({today.strftime('%Y-%m')}) ---")
    etl.process_month(today.year, today.month)