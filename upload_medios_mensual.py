import os
import datetime
import calendar
import dotenv
import pandas as pd
import mysql.connector
from mysql.connector import Error

dotenv.load_dotenv()

CONFIG = {
    "DB_HOST": os.getenv("DB_HOST", "localhost"),
    "DB_NAME": os.getenv("DB_NAME", "tu_base_de_datos"),
    "DB_USER": os.getenv("DB_USER", "root"),
    "DB_PASSWORD": os.getenv("DB_PASSWORD", ""),
}

# Nombres exactos de las métricas que subimos al glosario previamente
METRICS_NAMES = {
    "totales": "Total Media Mentions",
    "positivas": "Positive Media Mentions",
    "negativas": "Negative Media Mentions",
    "neutras": "Neutral Media Mentions"
}

class MediosMonthlyETL:
    def __init__(self):
        self.conn = self.get_db_connection()
        self.metrics_id_map = self.load_metrics_glosary()

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
                # Buscamos columnas clave para asegurar que es la fila correcta
                if 'Calificación' in row.values and 'Fecha' in row.values:
                    return index
            return 0 
        except Exception:
            return 0

    def process_file(self, filepath):
        print(f"📥 Leyendo el archivo '{filepath}'...")
        if not os.path.exists(filepath):
            print(f"❌ El archivo {filepath} no existe.")
            return

        # Leemos el archivo saltando cualquier fila basura al inicio
        header_idx = self._find_header_row(filepath)
        df = pd.read_csv(filepath, header=header_idx)

        # Validar si el archivo tiene el formato esperado
        if 'Calificación' not in df.columns or 'Fecha' not in df.columns:
            print("❌ Error: El archivo no tiene las columnas requeridas ('Calificación' o 'Fecha').")
            return

        # 1. Limpieza y cálculo de métricas
        # Convertimos todo a minúsculas y quitamos espacios para evitar errores (ej. " Positiva ")
        df['Calificación'] = df['Calificación'].astype(str).str.lower().str.strip()
        
        val_tot = int(len(df)) # El total de filas es el total de menciones
        val_pos = int((df['Calificación'] == 'positiva').sum())
        val_neg = int((df['Calificación'] == 'negativa').sum())
        val_neu = int((df['Calificación'] == 'neutra').sum())

        # 2. Obtener la fecha correcta
        # Analizamos la fecha más repetida para asegurar que pertenece al mes en curso
        fechas = pd.to_datetime(df['Fecha'], format='%Y-%m-%d', errors='coerce').dropna()
        if fechas.empty:
            print("❌ Error: No se pudieron parsear las fechas del archivo.")
            return
            
        year = int(fechas.dt.year.mode()[0])
        month = int(fechas.dt.month.mode()[0])
        
        # Conseguimos el último día del mes (ej. 28, 30 o 31)
        last_day = calendar.monthrange(year, month)[1]
        date_ref = datetime.date(year, month, last_day)

        print(f"   📊 Métricas calculadas para el periodo finalizado en {date_ref}:")
        print(f"      - Menciones Totales: {val_tot}")
        print(f"      - Positivas: {val_pos}")
        print(f"      - Negativas: {val_neg}")
        print(f"      - Neutras: {val_neu}")

        # 3. Subir a la Base de Datos
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
        
        # Hacemos Upsert para que puedas correr el script varias veces en el mismo mes sin duplicar
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
    # Asegúrate de colocar el CSV en la misma carpeta o poner la ruta correcta
    etl.process_file("menciones_medios_mensual.csv")