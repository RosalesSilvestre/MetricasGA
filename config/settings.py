# config/settings.py
import os
from dotenv import load_dotenv

load_dotenv()

CONFIG = {
    "DB_HOST": os.getenv("DB_HOST", "localhost"),
    "DB_NAME": os.getenv("DB_NAME"),
    "DB_USER": os.getenv("DB_USER"),
    "DB_PASSWORD": os.getenv("DB_PASSWORD"),
    
    "GA4_CREDENTIALS": os.getenv("GA4_CREDENTIALS_PATH"),
    "TOKEN_FILE": os.getenv("TOKEN_FILE"),
    "CLIENT_SECRETS_FILE": os.getenv("CLIENT_SECRETS_FILE"),
    "GOOGLE_SHEET_ID": os.getenv("GOOGLE_SHEET_ID"),
    
    "PROP_ITAM": os.getenv("ITAM_GA4_PROPERTY_ID"),
    "PROP_BLOG": os.getenv("ITAM_BLOG_GA4_PROPERTY_ID"),
    "PROP_CARRERAS_NEW": os.getenv("ITAM_CARRERAS_GA4_PROPERTY_ID_NEW"),
    "PROP_CARRERAS_OLD": os.getenv("ITAM_CARRERAS_GA4_PROPERTY_ID_OLD"),
}