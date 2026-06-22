import os
import datetime
import calendar
import pandas as pd
from mysql.connector import Error

import sys
import os

# Agrega la carpeta raíz del proyecto a las rutas del sistema para que encuentre 'config' y 'db'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importaciones centralizadas
from config.settings import CONFIG
from db.database import get_mysql_connection

METRICS_NAMES = {
    "totales": "Total Media Mentions",
    "positivas": "Positive Media Mentions",
    "negativas": "Negative Media Mentions",
    "neutras": "Neutral Media Mentions"
}

class MediosMonthlyETL:
    def __init__(self):
        self.conn = get_mysql_connection()
        self.metrics_id_map = self.load_metrics_glosary()

    def load_metrics_glosary(self):
        """Carga los IDs desde la tabla glosario_comunicacion dinámicamente"""
        if not self.conn: return {}
        cursor = self.conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT metrica, nombre FROM glosario_comunicacion")
            glosario_db = {row['nombre']: row['metrica'] for row in cursor.fetchall()}
            
            dynamic_map = {}
            for api_key, db_name in METRICS_NAMES.items():
                if db_name in glosario_db:
                    dynamic_map[api_key] = glosario_db[db_name]
                else:
                    print(f"⚠️ Métrica '{db_name}' no encontrada en el glosario_comunicacion.")
            return dynamic_map
        except Error as e:
            print(f"❌ Error leyendo glosario: {e}")
            return {}
        finally:
            cursor.close()

    def _find_header_row(self, filepath):
        """Escanea las primeras filas para buscar dónde empiezan realmente las columnas."""
        try:
            df_temp = pd.read_csv(filepath, nrows=10, header=None)
            for index, row in df_temp.iterrows():
                if 'Calificación' in row.values and 'Fecha' in row.values:
                    return index
            return 0 
        except Exception:
            return 0

    def process_file(self, filepath):
        print(f"📥 Leyendo el archivo de medios: '{filepath}'...")
        if not os.path.exists(filepath):
            print(f"❌ El archivo {filepath} no existe en el directorio principal.")
            return

        header_idx = self._find_header_row(filepath)
        df = pd.read_csv(filepath, header=header_idx)

        if 'Calificación' not in df.columns or 'Fecha' not in df.columns:
            print("❌ Error: El archivo no tiene las columnas requeridas ('Calificación' o 'Fecha').")
            return

        df['Calificación'] = df['Calificación'].astype(str).str.lower().str.strip()
        
        val_tot = int(len(df))
        val_pos = int((df['Calificación'] == 'positiva').sum())
        val_neg = int((df['Calificación'] == 'negativa').sum())
        val_neu = int((df['Calificación'] == 'neutra').sum())

        fechas = pd.to_datetime(df['Fecha'], format='%Y-%m-%d', errors='coerce').dropna()
        if fechas.empty:
            print("❌ Error: No se pudieron parsear las fechas del archivo.")
            return
            
        year = int(fechas.dt.year.mode()[0])
        month = int(fechas.dt.month.mode()[0])
        
        last_day = calendar.monthrange(year, month)[1]
        date_ref = datetime.date(year, month, last_day)

        print(f"   📊 Métricas calculadas para {date_ref}: Totales: {val_tot} | Positivas: {val_pos}")

        metrics_dict = {
            "totales": val_tot,
            "positivas": val_pos,
            "negativas": val_neg,
            "neutras": val_neu
        }
        self.insert_metrics(metrics_dict, date_ref)

    def insert_metrics(self, metrics_dict, date_ref):
        if not self.conn: return
        cursor = self.conn.cursor()
        
        sql = """
            INSERT INTO comunicacion (fecha, metrica, valor) 
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE valor = VALUES(valor)
        """
        data_to_insert = []
        
        for key, val in metrics_dict.items():
            mid = self.metrics_id_map.get(key)
            if mid: data_to_insert.append((date_ref, mid, val))
        
        if data_to_insert:
            try:
                cursor.executemany(sql, data_to_insert)
                self.conn.commit()
                print(f"✅ ¡Éxito! {len(data_to_insert)} registros guardados/actualizados en MySQL.")
            except Error as e:
                print(f"❌ Error insertando datos en BD: {e}")
        cursor.close()

if __name__ == "__main__":
    etl = MediosMonthlyETL()
    # Busca el archivo en el directorio raíz del proyecto
    etl.process_file("menciones_medios_mensual.csv")