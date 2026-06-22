# 📊 Sistema de Métricas: GA4, YouTube y Medios (ETL)

Este repositorio contiene el sistema automatizado de ETL (Extracción, Transformación y Carga) diseñado para unificar las métricas de **Google Analytics 4 (ITAM, Blog, Carreras)**, **YouTube Analytics** y **Menciones en Medios**.

El sistema centraliza la información en una base de datos **MySQL**, calcula métricas avanzadas (YTD, YoY, Previous FY) y actualiza automáticamente un dashboard en **Google Sheets** para su visualización.

---

## 📁 Estructura del Proyecto

El proyecto está diseñado con una arquitectura modular para facilitar su mantenimiento:

    MetricasGA/
    ├── config/
    │   ├── .env.example          # Plantilla de variables de entorno
    │   ├── settings.py           # Carga centralizada de credenciales
    │   └── get_credentials.py    # Generador de tokens para YouTube API
    ├── db/
    │   └── database.py           # Conexiones a MySQL (mysql.connector y SQLAlchemy)
    ├── etl/
    │   ├── extract_ga4_yt.py     # Extrae de GA4/YT y sube a MySQL
    │   └── extract_medios.py     # Lee el CSV manual de medios y sube a MySQL
    ├── reports/
    │   └── update_sheets.py      # Lee de MySQL, calcula métricas y actualiza Sheets
    ├── utils/
    │   ├── repair_historical.py       # Herramienta para recuperar datos históricos de GA4/YT
    │   └── upload_historico_medios.py # Herramienta para recuperar históricos de medios
    ├── docs/                     # Documentación técnica e historial de refactorización
    ├── requirements.txt          # Dependencias de Python
    └── README.md                 # Este manual operativo

---

## ⚙️ Configuración Inicial (Setup)

Si es la primera vez que configuras este proyecto en una computadora nueva, sigue estos pasos:

### 1. Entorno Virtual y Dependencias
Crea un entorno virtual e instala las dependencias:
    
    python -m venv venv
    
    # Activar en Windows:
    venv\Scripts\activate
    
    # Activar en Mac/Linux:
    source venv/bin/activate
    
    pip install -r requirements.txt

### 2. Variables de Entorno (.env)
1. Copia el archivo `config/.env.example` y renómbralo a `.env` en la raíz del proyecto.
2. Solicita las credenciales de la base de datos y los IDs de Google al administrador saliente y rellena los campos.
3. Asegúrate de tener el archivo JSON de la Service Account de Google Cloud en la ruta que especifiques en `GA4_CREDENTIALS_PATH`.

### 3. Autenticación de YouTube
A diferencia de GA4, YouTube requiere permisos de usuario real (OAuth2):
1. Asegúrate de tener el archivo `client_secrets.json` configurado en el `.env`.
2. Ejecuta el script de autorización:

    python config/get_credentials.py

3. Se abrirá una ventana en tu navegador. Inicia sesión con la cuenta de Google autorizada para ver el canal de YouTube. Al finalizar, se generará el archivo `token.json` necesario para operar.

---

## 📅 Manual de Operación (Día a Día)

### Tarea A: Actualización de Métricas Digitales (Web & YouTube)
*Frecuencia recomendada: Semanal o al cierre de mes.*

Este proceso consulta las APIs de Google para descargar el tráfico web y las vistas de video, insertándolas en la base de datos.

1. **Extraer datos a la Base de Datos:**

    python etl/extract_ga4_yt.py

   *(Nota: El script está diseñado para ser idempotente. Limpia y reescribe los datos del mes en curso y el mes anterior para asegurar precisión sin duplicar registros).*

2. **Actualizar el Google Sheet:**

    python reports/update_sheets.py

   *(Este script lee la información consolidada de MySQL, calcula acumulados (YTD, YoY) y actualiza las pestañas Analytics y Current Month en Google Sheets).*

---

### Tarea B: Carga de Menciones en Medios (Relaciones Públicas)
*Frecuencia: Mensual (cuando el proveedor entrega el reporte).*

Como estos datos no tienen API, se procesan a partir de un reporte manual.

1. Recibe el archivo .csv mensual de medios.
2. Guárdalo en la **carpeta raíz** de este proyecto con el nombre **EXACTO**: `menciones_medios_mensual.csv`.
3. Valida que el archivo contenga las columnas `Calificación` (positiva, negativa, neutra) y `Fecha` (formato YYYY-MM-DD).
4. **Procesar y subir a la BD:**

    python etl/extract_medios.py

5. **Actualizar el Google Sheet:**
   Ejecuta nuevamente el actualizador de reportes para que los nuevos datos de medios se reflejen en la nube:

    python reports/update_sheets.py

---

## 🚑 Solución de Problemas (Troubleshooting)

| Problema | Causa probable | Solución |
| :--- | :--- | :--- |
| **Falla YouTube / Error RefreshToken** | El `token.json` expiró o la sesión fue revocada. | Borra el archivo `token.json` actual y vuelve a correr `python config/get_credentials.py` para re-autenticar en el navegador. |
| **Error "No module named 'config'"** | Ejecución desde el directorio incorrecto. | Asegúrate de ejecutar siempre los scripts estando ubicado en la carpeta raíz del proyecto (`MetricasGA/`). |
| **Faltan métricas en el Dashboard** | Cruce de IDs incorrecto. | Valida la tabla `glosario_comunicacion` en MySQL. El sistema requiere que el nombre en código coincida exactamente con el ID de la base de datos. |
| **Faltan meses anteriores en la BD** | Hubo pausas en el servidor o fallos pasados. | Abre `utils/repair_historical.py`, ajusta las variables de fecha de inicio (`REPAIR_START_YEAR`) y corre el script para descargar el histórico faltante. |