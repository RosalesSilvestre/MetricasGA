import os
import glob
import pandas as pd
import dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError
import sys

# --- Configuración ---

# Carga las variables de entorno (DB_USER, DB_PASSWORD, DB_HOST, DB_NAME)
dotenv.load_dotenv()

# Diccionario de métricas (debe coincidir con main.py)
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

HISTORICAL_FOLDER = 'historical'

# --- Funciones de Base de Datos ---

def create_db_engine():
    """Crea y retorna un motor de conexión SQLAlchemy para MySQL."""
    try:
        db_user = os.getenv("DB_USER")
        db_pass = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST")
        db_name = os.getenv("DB_NAME")
        
        if not all([db_user, db_pass, db_host, db_name]):
            print("Error: Faltan variables de entorno (DB_USER, DB_PASSWORD, DB_HOST, DB_NAME).")
            sys.exit(1)
            
        # Usamos el driver mysql-connector-python
        connection_string = f"mysql+mysqlconnector://{db_user}:{db_pass}@{db_host}/{db_name}"
        engine = create_engine(connection_string)
        
        # Prueba la conexión
        with engine.connect() as conn:
            pass
        print(f"✅ Conexión exitosa a la base de datos '{db_name}' en '{db_host}'.")
        return engine
        
    except OperationalError as e:
        print(f"❌ Error de conexión: ¿Credenciales correctas? ¿Servidor activo?")
        print(f"Detalle: {e}")
        sys.exit(1)
    except ImportError:
        print("❌ Error: Driver 'mysql-connector-python' no encontrado.")
        print("Asegúrate de instalarlo con: pip install mysql-connector-python")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error inesperado al crear el motor de BBDD: {e}")
        sys.exit(1)

def populate_glossary(engine):
    """
    Inserta o actualiza el glosario de métricas en la tabla 'glosario_comunicacion'.
    Usa 'ON DUPLICATE KEY UPDATE' para ser idempotente.
    """
    print("Sincronizando el glosario de métricas...")
    
    # Convertir el diccionario a una lista de tuplas
    metrics_data = list(METRICS_DICT.items())
    
    # SQL para insertar o actualizar (idempotente)
    # Esto asegura que si la 'metrica' (PK) ya existe, solo actualiza el 'nombre'
    insert_query = """
    INSERT INTO glosario_comunicacion (metrica, nombre)
    VALUES (%s, %s)
    ON DUPLICATE KEY UPDATE nombre = VALUES(nombre)
    """
    
    try:
        with engine.connect() as conn:
            # Para ejecutar 'executemany', necesitamos la conexión raw de mysql-connector
            # Obtenemos la conexión subyacente de DBAPI
            raw_conn = conn.connection
            with raw_conn.cursor() as cursor:
                cursor.executemany(insert_query, metrics_data)
                raw_conn.commit()
            
        print(f"Glosario actualizado con {len(metrics_data)} métricas.")
    
    except (ProgrammingError, OperationalError) as e:
        print(f"❌ Error al poblar el glosario: ¿La tabla 'glosario_comunicacion' existe?")
        print(f"Detalle: {e}")
    except Exception as e:
        print(f"❌ Error inesperado al poblar el glosario: {e}")


def get_processed_dates(engine):
    """
    Consulta la BBDD para obtener un set de todas las fechas (en formato YYYY-MM-DD)
    que ya han sido insertadas en la tabla 'comunicacion'.
    """
    print("Consultando fechas ya procesadas en la base de datos...")
    processed_dates = set()
    try:
        with engine.connect() as conn:
            # Aseguramos que la fecha se formatee como 'YYYY-MM-DD'
            result = conn.execute(text("SELECT DISTINCT DATE_FORMAT(fecha, '%Y-%m-%d') FROM comunicacion"))
            for row in result:
                processed_dates.add(row[0])
        print(f"Fechas encontradas en la BBDD: {len(processed_dates)}")
        return processed_dates
        
    except (ProgrammingError, OperationalError) as e:
        print(f"⚠️ Advertencia: No se pudo obtener fechas (¿tabla 'comunicacion' vacía o no existe?).")
        print(f"Detalle: {e}")
        return processed_dates # Retorna un set vacío
    except Exception as e:
        print(f"❌ Error inesperado al consultar fechas: {e}")
        return processed_dates


# --- Funciones de Archivos y Carga ---

def find_new_files(processed_dates):
    """
    Busca en la carpeta /historical los CSVs cuya fecha NO ESTÉ en el set de processed_dates.
    CRITICAL: Solo busca en 'historical/' y explícitamente ignora 'staging/' para garantizar
    que los datos parciales nunca se mezclen con los datos finalizados.
    """
    print("Buscando nuevos archivos CSV en 'historical/'...")
    print("⚠️  IMPORTANTE: Solo se procesarán archivos de 'historical/'. Los archivos de 'staging/' serán ignorados.")
    
    # Explicitly search only in historical folder
    all_files = glob.glob(os.path.join(HISTORICAL_FOLDER, 'results_*.csv'))
    new_files = []
    
    # Additional safeguard: filter out any staging files if they somehow appear
    staging_files = glob.glob(os.path.join('staging', '*.csv'))
    if staging_files:
        print(f"⚠️  Advertencia: Se detectaron {len(staging_files)} archivo(s) en 'staging/'. Estos serán ignorados.")
        for sf in staging_files:
            print(f"   Ignorando: {sf}")
    
    if not all_files:
        print("No se encontraron archivos CSV en 'historical/'.")
        return []
        
    for f in all_files:
        # Additional safeguard: explicitly reject staging folder paths
        if 'staging' in f.lower():
            print(f"⚠️  Advertencia: Archivo rechazado (contiene 'staging' en la ruta): {f}")
            continue
            
        # Extrae la fecha del nombre de archivo. Ej: 'historical/results_2024-10-31.csv'
        try:
            date_str = os.path.basename(f).split('_')[-1].replace('.csv', '')
            # Valida el formato YYYY-MM-DD
            pd.to_datetime(date_str, format='%Y-%m-%d')
            
            if date_str not in processed_dates:
                new_files.append((f, date_str))
        except (IndexError, ValueError):
            print(f"Advertencia: Ignorando archivo con formato de nombre incorrecto: {f}")
            
    print(f"✅ Se encontraron {len(new_files)} archivos nuevos para procesar desde 'historical/'.")
    return new_files

def process_and_upload(files_to_process, engine):
    """
    Lee, transforma y sube los DataFrames de los archivos nuevos a la BBDD.
    """
    if not files_to_process:
        print("No hay archivos nuevos para subir. Proceso finalizado.")
        return

    for filepath, date_str in files_to_process:
        print(f"Procesando archivo: {filepath}...")
        try:
            df = pd.read_csv(filepath)
            
            # 1. Renombrar columnas para que coincidan con la BBDD
            df.rename(columns={
                'Date': 'fecha',
                'Metric': 'metricas',
                'Value': 'valor'
            }, inplace=True)
            
            # 2. Asegurar tipos de datos correctos
            df['fecha'] = pd.to_datetime(df['fecha'])
            df['metricas'] = df['metricas'].astype('int64') # BIGINT
            df['valor'] = df['valor'].astype('float')    # DOUBLE
            
            # 3. Cargar a la BBDD
            # Usamos if_exists='append' e index=False
            # 'index=False' es crucial para no subir el índice de pandas
            # La BBDD se encargará de la 'id' autoincremental
            df.to_sql(
                'comunicacion',
                con=engine,
                if_exists='append',
                index=False
            )
            
            print(f"✅ Datos del {date_str} subidos correctamente ({len(df)} filas).")

        except pd.errors.EmptyDataError:
            print(f"Advertencia: El archivo {filepath} está vacío. Ignorando.")
        except Exception as e:
            print(f"❌ Error al procesar o subir el archivo {filepath}: {e}")
            print("Se detiene el proceso para evitar cargas parciales.")
            break # Detener en caso de error

# --- Ejecución Principal ---

def main():
    """Orquesta todo el proceso de ETL."""
    print("🚀 Iniciando script de carga a MySQL...")
    print("📋 Este script SOLO procesa archivos de 'historical/'. Los datos de 'staging/' nunca se cargarán a MySQL.")
    
    # 1. Conectar a la BBDD
    engine = create_db_engine()
    
    # 2. Sincronizar tabla de glosario
    populate_glossary(engine)
    
    # 3. Obtener fechas ya procesadas
    processed_dates = get_processed_dates(engine)
    
    # 4. Encontrar archivos nuevos (solo de historical/)
    new_files = find_new_files(processed_dates)
    
    # 5. Procesar y subir archivos nuevos
    process_and_upload(new_files, engine)
    
    print("✨ Proceso de carga de datos completado.")

if __name__ == "__main__":
    main()