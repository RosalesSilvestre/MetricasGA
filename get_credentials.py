import os
import dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

# Cargamos las variables de entorno desde el archivo .env
dotenv.load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']
CLIENT_SECRETS_FILE = os.getenv("CLIENT_SECRETS_FILE")
TOKEN_FILE = os.getenv("TOKEN_FILE")

def get_credentials():
    """
    Realiza el flujo de autenticación interactivo para obtener las credenciales.
    """
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    
    # Esto abrirá una ventana en tu navegador para que inicies sesión y des tu consentimiento.
    print("Iniciando el flujo de autorización en tu navegador...")
    credentials = flow.run_local_server(port=0)
    
    # Guardamos las credenciales (incluyendo el refresh_token) para uso futuro.
    with open(TOKEN_FILE, 'w') as token_file:
        token_file.write(credentials.to_json())
    
    print(f"\n¡Perfecto! Las credenciales se han guardado en el archivo '{TOKEN_FILE}'")

if __name__ == '__main__':
    # Si el token ya existe, no hacemos nada para evitar pedir permiso de nuevo.
    if os.path.exists(TOKEN_FILE):
        print(f"El archivo '{TOKEN_FILE}' ya existe. No es necesario volver a autenticarse.")
    else:
        get_credentials()