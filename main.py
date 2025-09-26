import os
import dotenv
import pandas as pd
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    Filter,
    FilterExpression
)

dotenv.load_dotenv()

# This dictionary is provisionary to store the metrics name and number for the results file and the Database

metrics_dict = {
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

# Date of the new installation of the GA4 property for carreras.itam.mx
FECHA_NUEVA_INSTALACION = '2024-10-01'
def fetch_google_analytics_data(StartDate, EndDate):
    """Fetches data from Google Analytics for the specified properties and date range."""

    # Configuration
    # Properties to fetch data from
    properties = {}

    properties['itam.mx'] = os.getenv("ITAM_GA4_PROPERTY_ID")
    if not properties['itam.mx']:
        raise ValueError("ITAM_GA4_PROPERTY_ID environment variable is not set.")
    
    properties['blog.itam.mx'] = os.getenv("ITAM_BLOG_GA4_PROPERTY_ID")
    if not properties['blog.itam.mx']:
        raise ValueError("ITAM_BLOG_GA4_PROPERTY_ID environment variable is not set.")

    if (EndDate >= FECHA_NUEVA_INSTALACION):
        properties['carreras.itam.mx'] = os.getenv("ITAM_CARRERAS_GA4_PROPERTY_ID_NEW")
    else:
        properties['carreras.itam.mx'] = os.getenv("ITAM_CARRERAS_GA4_PROPERTY_ID_OLD")
        print("Aplicando filtro de hostName para la propiedad antigua de carreras.itam.mx")
        carreras_filter = FilterExpression(
            filter=Filter(
                field_name="hostName",
                string_filter=Filter.StringFilter(
                    match_type=Filter.StringFilter.MatchType.EXACT,
                    value="aspirantes.itam.mx"
                )
            )
        )

    if not properties['carreras.itam.mx']:
            raise ValueError("ITAM_CARRERAS_GA4_PROPERTY_ID_NEW environment variable is not set.")
    else:
        properties['carreras.itam.mx'] = os.getenv("ITAM_CARRERAS_GA4_PROPERTY_ID_OLD")
        if not properties['carreras.itam.mx']:
            raise ValueError("ITAM_CARRERAS_GA4_PROPERTY_ID_OLD environment variable is not set.")

    # Credentials for Google Analytics Data API
    GA4_CREDENTIALS_PATH = os.getenv("GA4_CREDENTIALS_PATH")

    if not GA4_CREDENTIALS_PATH:
        raise ValueError("GA4_CREDENTIALS_PATH environment variable is not set.")

    ga4_credentials= service_account.Credentials.from_service_account_file(
        GA4_CREDENTIALS_PATH,
        scopes=["https://www.googleapis.com/auth/analytics.readonly"]
    )

    # Creates a client for the Google Analytics Data API
    client = BetaAnalyticsDataClient(credentials=ga4_credentials)
    
    #Defines the metrics and dimensions to fetch
    metrics_list = ["totalUsers","screenPageViews",  "screenPageViewsPerSession"]
    dimensions_list = []

    # Transforms the list of metrics,dimensions and the date_ranges into the required format
    metrics = [
        Metric(name=metric) for metric in metrics_list
    ]
    
    dimensions = [
        Dimension(name=dimension) for dimension in dimensions_list
    ]
    date_ranges = [
        DateRange(start_date=StartDate, end_date=EndDate)
    ]
    
    # Creates the request for both properties
    request_itam = RunReportRequest(
        property=f"properties/{properties['itam.mx']}",
        metrics=metrics,
        date_ranges=date_ranges,
        dimensions=dimensions
    )

    request_blog = RunReportRequest(
        property=f"properties/{properties['blog.itam.mx']}",
        metrics=metrics,
        date_ranges=date_ranges,
        dimensions=dimensions
    )

    request_carreras = RunReportRequest(
        property=f"properties/{properties['carreras.itam.mx']}",
        metrics=metrics,
        date_ranges=date_ranges,
        dimensions=dimensions,
        dimension_filter=carreras_filter if 'carreras_filter' in locals() else None
    )
    # Declares the dictonary to store the results
    results = {}

    # Fetches the data for both properties
    try:
        # Fetches the data for itam.mx
        response_itam = client.run_report(request_itam)

        #Parse the response into a dictionary
        if not response_itam.rows:
            print("No data found for itam.mx")
            results['itam.mx'] = {}
        else:
            results['itam.mx'] = {
                "totalUsers": [int(row.metric_values[0].value) for row in response_itam.rows],
                "views": [int(row.metric_values[1].value) for row in response_itam.rows],
                "viewsPerSession": [round(float(row.metric_values[2].value),2) for row in response_itam.rows],
            }
    except Exception as e:
        print(f"Error fetching data for itam.mx: {e}")
        response_itam = None
    try:
        # Fetches the data for blog.itam.mx
        response_blog = client.run_report(request_blog)

        #Parse the response into a dictionary
        if not response_blog.rows:
            print("No data found for blog.itam.mx")
            results['blog.itam.mx'] = {}
        else:
            results['blog.itam.mx'] = {
                "totalUsers": [int(row.metric_values[0].value) for row in response_blog.rows],
                "views": [int(row.metric_values[1].value) for row in response_blog.rows],
                "viewsPerSession": [round(float(row.metric_values[2].value),2) for row in response_blog.rows],
            }

    except Exception as e:
        print(f"Error fetching data for blog.itam.mx: {e}")
        response_blog = None

    try:
        # Fetches the data for carreras.itam.mx
        response_carreras = client.run_report(request_carreras)

        #Parse the response into a dictionary
        if not response_carreras.rows:
            print("No data found for carreras.itam.mx")
            results['carreras.itam.mx'] = {}
        else:
            results['carreras.itam.mx'] = {
                "totalUsers": [int(row.metric_values[0].value) for row in response_carreras.rows],
                "views": [int(row.metric_values[1].value) for row in response_carreras.rows],
                "viewsPerSession": [round(float(row.metric_values[2].value),2) for row in response_carreras.rows],
            }
    except Exception as e:
        print(f"Error fetching data for carreras.itam.mx: {e}")
        response_carreras = None

    return results

def fetch_youtube_analytics_data( start_date, end_date):
    # --- Configuration ---
    # The file client_secret.json contains your OAuth 2.0 client credentials.
    CLIENT_SECRETS_FILE = os.getenv("CLIENT_SECRETS_FILE")

    if not CLIENT_SECRETS_FILE:
        raise ValueError("CLIENT_SECRETS_FILE environment variable is not set.")

    # The scope for the YouTube Analytics API.
    # This scope allows access to YouTube Analytics data.
    SCOPES = ["https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/yt-analytics.readonly"]

    # Path to store the user's access and refresh tokens.
    TOKEN_FILE = os.getenv("TOKEN_FILE")

    if not TOKEN_FILE:
        raise ValueError("TOKEN_FILE environment variable is not set.")

    """Authenticates with Google and returns a YouTube Analytics service object."""
    credentials = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(TOKEN_FILE):
        credentials = Credentials.from_authorized_user_file(
            TOKEN_FILE, SCOPES
        )

    youtube_analytics_service =build("youtubeAnalytics", "v2", credentials=credentials)

    # --- Main Script ---
    try:
        response = youtube_analytics_service.reports().query(
            ids=f"channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views",
            dimensions="insightTrafficSourceType",
            #sort="month"
        ).execute()

        results = []
        if "rows" in response:
            for row in response["rows"]:
                source = row[0]
                views = row[1]
                results.append({
                    "source": source,
                    "views": views
                })
        return results

    except HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred: {e.content}")
        return []

def update_google_sheet(google_analytics_data, youtube_analytics_data):
    """
    Updates a Google Sheet with the provided analytics data.
    """
    try:
        # --- Configuration for Google Sheets ---
        GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
        if not GOOGLE_SHEET_ID:
            raise ValueError("GOOGLE_SHEET_ID environment variable is not set.")

        GOOGLE_SHEETS_CREDENTIALS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")
        if not GOOGLE_SHEETS_CREDENTIALS_PATH:
            raise ValueError("GOOGLE_SHEETS_CREDENTIALS_PATH environment variable is not set.")

        SHEET_NAME = "Analytics" # Or the name of the sheet you want to update
        
        # --- Authentication ---
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_SHEETS_CREDENTIALS_PATH,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()

        # --- Prepare the data for the sheet ---
        # Get the first value from the lists, or use 0 if the list is empty
        itam_total_users = google_analytics_data.get('itam.mx', {}).get('totalUsers', [0])[0]
        itam_views = google_analytics_data.get('itam.mx', {}).get('views', [0])[0]
        itam_views_per_session = google_analytics_data.get('itam.mx', {}).get('viewsPerSession', [0])[0]

        blog_total_users = google_analytics_data.get('blog.itam.mx', {}).get('totalUsers', [0])[0]
        blog_views = google_analytics_data.get('blog.itam.mx', {}).get('views', [0])[0]
        blog_views_per_session = google_analytics_data.get('blog.itam.mx', {}).get('viewsPerSession', [0])[0]

        carreras_total_users = google_analytics_data.get('carreras.itam.mx', {}).get('totalUsers', [0])[0]
        carreras_views = google_analytics_data.get('carreras.itam.mx', {}).get('views', [0])[0]
        carreras_views_per_session = google_analytics_data.get('carreras.itam.mx', {}).get('viewsPerSession', [0])[0]

        # Calculate YouTube views
        ad_views = sum(int(entry['views']) for entry in youtube_analytics_data if entry['source'] == 'ADVERTISING')
        total_views = sum(int(entry['views']) for entry in youtube_analytics_data)
        organic_views = total_views - ad_views

        # Define the data to be written
        values = [
            ["Metric", "Value"],
            ["ITAM Total Users", itam_total_users],
            ["ITAM Views", itam_views],
            ["ITAM Views Per Session", itam_views_per_session],
            ["Blog Total Users", blog_total_users],
            ["Blog Views", blog_views],
            ["Blog Views Per Session", blog_views_per_session],
            ["Carreras Total Users", carreras_total_users],
            ["Carreras Views", carreras_views],
            ["Carreras Views Per Session", carreras_views_per_session],
            ["YouTube Advertisement Views", ad_views],
            ["YouTube Organic Views", organic_views],
            ["YouTube Total Views", total_views]
        ]

        # --- Write data to the sheet ---
        body = {
            'values': values
        }
        result = sheet.values().update(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="RAW",
            body=body
        ).execute()
        print(f"{result.get('updatedCells')} cells updated in Google Sheet.")

    except HttpError as err:
        print(err)
    except Exception as e:
        print(f"An error occurred: {e}")
        return
    
def main(StartDate, EndDate):
    """Main function to execute the script.
    It gets the metrics from Google Analytics, then from YouTube Analytics, and finally from Report Files
    
    and saves the results to a CSV file."""
    # Fetch Google Analytics data
    google_analytics_data = fetch_google_analytics_data(StartDate, EndDate)

    print("Google Analytics Data:")
    for property_name, data in google_analytics_data.items():
        print(f"{property_name}:")
        print(f"  Total Users: {data.get('totalUsers', 'No data')[0]}")
        print(f"  Views: {data.get('views', 'No data')[0]}")
        print(f"  Views per Session: {data.get('viewsPerSession', 'No data')[0]}")

    # Fetch YouTube Analytics data
    youtube_analytics_data = fetch_youtube_analytics_data(StartDate, EndDate)

    update_google_sheet(google_analytics_data, youtube_analytics_data)
    print("\nYouTube Analytics Data:")
    for entry in youtube_analytics_data:
        print(f"  Source: {entry['source']}, Views: {entry['views']}")

    # Calculates advertisement views and total views from YouTube data
    ad_views = sum(int(entry['views']) for entry in youtube_analytics_data if entry['source'] == 'ADVERTISING')
    total_views = sum(int(entry['views']) for entry in youtube_analytics_data)
    organic_views = total_views - ad_views

    print(f"\nYouTube Advertisement Views: {ad_views}")
    print(f"YouTube Organic Views: {organic_views}")
    print(f"YouTube Total Views: {total_views}")

    #generates a dataframe with three columns (date, metric, value) for both GA and YouTube data
    #and saves it to a CSV file

    combined_data = []
    # Process metrics in the order defined by metrics_dict
    for metric_number, metric_name in metrics_dict.items():
        if "ITAM" in metric_name:
            property_key = "itam.mx"
        elif "Blog" in metric_name:
            property_key = "blog.itam.mx"
        elif "Carreras" in metric_name:
            property_key = "carreras.itam.mx"
        else:
            continue  # Skip YouTube metrics here; handled below

        # Map metric_name to the key used in google_analytics_data
        if "Total Users" in metric_name:
            metric_key = "totalUsers"
        elif "Views Per Session" in metric_name:
            metric_key = "viewsPerSession"
        elif "Views" in metric_name:
            metric_key = "views"
        else:
            continue

        value = google_analytics_data.get(property_key, {}).get(metric_key, [0])[0]
        combined_data.append({
            "Date": EndDate,
            "Metric": metric_number,
            "Value": value
        })

    for metric_name, metric_number in [("YouTube Advertisement Views", 10), ("YouTube Organic Views", 11), ("YouTube Total Views", 12)]:
        if metric_name == "YouTube Advertisement Views":
            value = ad_views
        elif metric_name == "YouTube Organic Views":
            value = organic_views
        elif metric_name == "YouTube Total Views":
            value = total_views
        combined_data.append({
            "Date": EndDate,
            "Metric": metric_number,
            "Value": value
        })
    combined_df = pd.DataFrame(combined_data)
    print(combined_df.head(20))

    return combined_df

def get_dates(date):
    """Given a date in 'YYYY-MM-DD' format, returns the first and last date of that month."""
    year, month, _ = map(int, date.split('-'))
    first_date = f"{year}-{month:02d}-01"
    if month == 12:
        last_date = f"{year}-12-31"
    else:
        next_month = month + 1
        last_date = f"{year}-{next_month:02d}-01"
        last_date = pd.to_datetime(last_date) - pd.Timedelta(days=1)
        last_date = last_date.strftime('%Y-%m-%d')
    return first_date, last_date

if __name__ == "__main__":
    #this will iterate for all the months from january 2024 to the current month in order to generate the historical data
    do_historical = False
    if not do_historical:
        # Get the current date in 'YYYY-MM-DD' format and changes it for the last day of the last month
        current_date = pd.Timestamp.now().replace(day=1) - pd.Timedelta(days=1)
        current_date = current_date.strftime('%Y-%m-%d')
        #current_date = '2024-01-01'  # For testing purposes, you can set a fixed date here
        # Get the first and last date of the current month
        start_date, end_date = get_dates(current_date)
        print(f"Fetching data from {start_date} to {end_date}")
        result = main(start_date, end_date)
        #saves the results to a CSV file
        result.to_csv(f"historical/results_{current_date}.csv", index=False)
        print("Results saved to historical/results.csv")
        exit(0)
    else:
        print("Generating historical data from January 2024 to the current month")
        if not os.path.exists('historical'):
            os.makedirs('historical')
        for fecha in pd.date_range(start='2024-01-31', end=pd.Timestamp.now(), freq='MS').strftime('%Y-%m-%d'):
            print(f"Processing data for the month of {fecha}")
            result=main(get_dates(fecha)[0], get_dates(fecha)[1])
            #saves the results to a CSV file
            result.to_csv(f"historical/results_{fecha}.csv", index=False)
    


