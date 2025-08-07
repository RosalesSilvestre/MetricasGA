import os
import dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest
)

dotenv.load_dotenv()

def fetch_google_analytics_data(StartDate, EndDate):
    """Fetches data from Google Analytics for the specified properties and date range."""

    # Configuration
    # Properties to fetch data from
    properties = { 'itam.mx': 392120488, 'blog.itam.mx': 392065347}

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

    # If there are no (valid) credentials available, let the user log in.
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, SCOPES
            )
            # You might need to change the redirect_uri depending on your application type.
            # For desktop apps, 'urn:ietf:wg:oauth:2.0:oob' is common.
            # For web apps, it would be a URL.
            credentials = flow.run_local_server(port=0) # Automatically opens browser for authentication
        # Save the credentials for the next run
        with open(TOKEN_FILE, "w") as token:
            token.write(credentials.to_json())

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

if __name__ == "__main__":
    main('2025-01-01', '2025-01-31')
    