import os
import datetime
import calendar
from mysql.connector import Error

import sys
import os

# Agrega la carpeta raíz del proyecto a las rutas del sistema para que encuentre 'config' y 'db'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importaciones centralizadas (Arquitectura nueva)
from config.settings import CONFIG
from db.database import get_mysql_connection

# Google Libraries
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta import types 
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials 

# Puente entre el código Python y el nombre oficial en la BD
API_TO_DB_NAME = {
    "itam_users": "ITAM Total Users",
    "itam_views": "ITAM Views", 
    "itam_views_per_session": "ITAM Views Per Session",
    "blog_users": "Blog Total Users", 
    "blog_views": "Blog Views", 
    "blog_views_per_session": "Blog Views Per Session",
    "carreras_users": "Carreras Total Users", 
    "carreras_views": "Carreras Views", 
    "carreras_views_per_session": "Carreras Views Per Session",
    "youtube_ads": "YouTube Advertisement Views", 
    "youtube_organic": "YouTube Organic Views", 
    "youtube_total": "YouTube Total Views"
}

class MetricsETL:
    def __init__(self):
        self.conn = get_mysql_connection()
        self.metrics_id_map = self.load_metrics_glosary()
        self.ga4_client = self.init_ga4()
        self.yt_service = self.init_youtube()

    def load_metrics_glosary(self):
        """Carga los IDs desde la tabla glosario_comunicacion"""
        if not self.conn: return {}
        cursor = self.conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT metrica, nombre FROM glosario_comunicacion")
            glosario_db = {row['nombre']: row['metrica'] for row in cursor.fetchall()}
            
            dynamic_map = {}
            for api_key, db_name in API_TO_DB_NAME.items():
                if db_name in glosario_db:
                    dynamic_map[api_key] = glosario_db[db_name]
                else:
                    print(f"⚠️ Métrica '{db_name}' no encontrada en el glosario.")
            return dynamic_map
        except Error as e:
            print(f"❌ Error leyendo glosario: {e}")
            return {}
        finally:
            cursor.close()

    def init_ga4(self):
        if not CONFIG.get("GA4_CREDENTIALS"): return None
        creds = service_account.Credentials.from_service_account_file(
            CONFIG["GA4_CREDENTIALS"], scopes=["https://www.googleapis.com/auth/analytics.readonly"]
        )
        return BetaAnalyticsDataClient(credentials=creds)

    def init_youtube(self):
        token_path = CONFIG.get("TOKEN_FILE")
        if not token_path or not os.path.exists(token_path): return None
        creds = Credentials.from_authorized_user_file(
            token_path, ["https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/yt-analytics.readonly"]
        )
        return build("youtubeAnalytics", "v2", credentials=creds)

    def clean_month_data(self, year, month):
        if not self.conn: return
        cursor = self.conn.cursor()
        ids_to_clean = tuple(self.metrics_id_map.values())
        if not ids_to_clean: return
        
        format_strings = ','.join(['%s'] * len(ids_to_clean))
        query = f"DELETE FROM comunicacion WHERE YEAR(fecha) = %s AND MONTH(fecha) = %s AND metrica IN ({format_strings})"
        try:
            cursor.execute(query, (year, month, *ids_to_clean))
            self.conn.commit()
            print(f"🧹 Datos limpiados en BD para {year}-{month:02d}")
        except Error as err:
            print(f"❌ Error borrando datos: {err}")
        finally:
            cursor.close()

    def fetch_ga4_single_property(self, property_id, start_date, end_date, dimension_filter=None):
        if not self.ga4_client or not property_id: return (0, 0, 0.0)
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
            if not response.rows: return (0, 0, 0.0)
            row = response.rows[0]
            return (int(row.metric_values[0].value), int(row.metric_values[1].value), round(float(row.metric_values[2].value), 2))
        except Exception as e:
            print(f"🔥 Error GA4 (Prop ID {property_id}): {e}")
            return (0, 0, 0.0)

    def fetch_all_metrics(self, start_date, end_date):
        print(f"   🔎 Consultando APIs de {start_date} a {end_date}...")
        itam_u, itam_v, itam_vps = self.fetch_ga4_single_property(CONFIG["PROP_ITAM"], start_date, end_date)
        blog_u, blog_v, blog_vps = self.fetch_ga4_single_property(CONFIG["PROP_BLOG"], start_date, end_date)

        carreras_id, carreras_filter = None, None
        fecha_nueva_instalacion = '2024-10-01'
        
        if end_date >= fecha_nueva_instalacion:
            carreras_id = CONFIG["PROP_CARRERAS_NEW"]
        else:
            carreras_id = CONFIG["PROP_CARRERAS_OLD"]
            carreras_filter = types.FilterExpression(
                filter=types.Filter(
                    field_name="hostName",
                    string_filter=types.Filter.StringFilter(match_type=types.Filter.StringFilter.MatchType.EXACT, value="aspirantes.itam.mx")
                )
            )

        carr_u, carr_v, carr_vps = self.fetch_ga4_single_property(carreras_id, start_date, end_date, carreras_filter)

        yt_ads, yt_org, yt_tot = (0, 0, 0)
        if self.yt_service:
            try:
                response = self.yt_service.reports().query(
                    ids="channel==MINE", startDate=start_date, endDate=end_date,
                    metrics="views", dimensions="insightTrafficSourceType"
                ).execute()
                for row in response.get('rows', []):
                    views = int(row[1])
                    yt_tot += views
                    if row[0] == 'ADVERTISING': yt_ads += views
                yt_org = yt_tot - yt_ads
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
            mid = self.metrics_id_map.get(key)
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
        
        end_date_obj = today if start_date.year == today.year and start_date.month == today.month else datetime.date(year, month, last_day) 
        
        self.clean_month_data(year, month)
        metrics = self.fetch_all_metrics(start_date.strftime('%Y-%m-%d'), end_date_obj.strftime('%Y-%m-%d'))
        self.insert_metrics(metrics, end_date_obj)
        print("✅ Listo.\n")

if __name__ == "__main__":
    print("🚀 Iniciando extracción de GA4 y YouTube...")
    etl = MetricsETL()
    today = datetime.date.today()
    
    first = today.replace(day=1)
    prev = first - datetime.timedelta(days=1)
    
    print(f"--- 1. Ejecutando Mes Anterior ({prev.strftime('%Y-%m')}) ---")
    etl.process_month(prev.year, prev.month)
    
    print(f"--- 2. Ejecutando Mes Actual ({today.strftime('%Y-%m')}) ---")
    etl.process_month(today.year, today.month)