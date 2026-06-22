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

# Definición de las nuevas métricas (ID, Nombre) para el glosario
NUEVAS_METRICAS = [
    (13, "Total Media Mentions"),
    (14, "Positive Media Mentions"),
    (15, "Negative Media Mentions"),
    (16, "Neutral Media Mentions")
]

MONTH_MAP = {
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12
}

def get_db_connection():
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

def main():
    csv_path = 'menciones_medios.csv'
    if not os.path.exists(csv_path):
        print(f"⚠️ No se encontró el archivo: {csv_path}")
        return

    conn = get_db_connection()
    if not conn: return
    cursor = conn.cursor()

    # --- 1. ACTUALIZAR EL GLOSARIO ---
    print("📖 Actualizando tabla glosario_comunicacion...")
    sql_glosario = "INSERT IGNORE INTO glosario_comunicacion (metrica, nombre) VALUES (%s, %s)"
    try:
        cursor.executemany(sql_glosario, NUEVAS_METRICAS)
        conn.commit()
        print("✅ Glosario actualizado (o ya contenía las métricas).")
    except Error as e:
        print(f"❌ Error actualizando glosario: {e}")
        return

    # --- 2. PROCESAR EL CSV HISTÓRICO ---
    print("📥 Leyendo archivo CSV...")
    df = pd.read_csv(csv_path).iloc[:4]
    
    start_collecting = False
    cols_to_process = []
    for col in df.columns:
        if col == 'ene-24': start_collecting = True
        if start_collecting and '-' in str(col): 
            cols_to_process.append(col)
    
    # --- CAMBIO IMPORTANTE: UPSERT EN LUGAR DE INSERT NORMAL ---
    # Si la combinación fecha-métrica existe, actualiza el valor.
    sql_datos = """
        INSERT INTO comunicacion (fecha, metrica, valor) 
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE valor = VALUES(valor)
    """
    
    data_to_insert = []
    
    for col in cols_to_process:
        mes_str, yy_str = col.split('-')
        year = 2000 + int(yy_str)
        month = MONTH_MAP[mes_str.lower()]
        last_day = calendar.monthrange(year, month)[1]
        date_ref = datetime.date(year, month, last_day)
        
        val_tot = int(float(df.loc[0, col])) if pd.notna(df.loc[0, col]) else 0
        val_pos = int(float(df.loc[1, col])) if pd.notna(df.loc[1, col]) else 0
        val_neg = int(float(df.loc[2, col])) if pd.notna(df.loc[2, col]) else 0
        val_neu = int(float(df.loc[3, col])) if pd.notna(df.loc[3, col]) else 0
        
        data_to_insert.extend([
            (date_ref, 13, val_tot),
            (date_ref, 14, val_pos),
            (date_ref, 15, val_neg),
            (date_ref, 16, val_neu)
        ])
    
    if data_to_insert:
        try:
            cursor.executemany(sql_datos, data_to_insert)
            conn.commit()
            print(f"✅ ¡Éxito! {len(data_to_insert)} registros guardados/actualizados en la BD.")
        except Error as e:
            print(f"❌ Error insertando datos históricos: {e}")
            
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()