# db/database.py
import mysql.connector
from sqlalchemy import create_engine
from mysql.connector import Error
from config.settings import CONFIG

def get_mysql_connection():
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

def get_sqlalchemy_engine():
    try:
        user = CONFIG["DB_USER"]
        password = CONFIG["DB_PASSWORD"]
        host = CONFIG["DB_HOST"]
        db_name = CONFIG["DB_NAME"]
        return create_engine(f'mysql+mysqlconnector://{user}:{password}@{host}/{db_name}')
    except Exception as e:
        print(f"❌ Error creando motor SQLAlchemy: {e}")
        return None