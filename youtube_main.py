import os
import datetime
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- Configuration ---
# The file client_secret.json contains your OAuth 2.0 client credentials.
CLIENT_SECRETS_FILE = "client_secret.json"

# The scope for the YouTube Analytics API.
# This scope allows access to YouTube Analytics data.
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly",
          "https://www.googleapis.com/auth/yt-analytics.readonly"]

# Path to store the user's access and refresh tokens.
TOKEN_FILE = "token.json"

# --- Authentication Function ---
def get_authenticated_service():
    """Authenticates with Google and returns a YouTube Analytics service object."""
    credentials = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(TOKEN_FILE):
        credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

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

    return build("youtubeAnalytics", "v2", credentials=credentials)

# --- Main Script ---
def get_monthly_views_by_source(youtube_analytics_service, channel_id, start_date_str, end_date_str):
    """
    Retrieves monthly views by traffic source for a given channel and date range.

    Args:
        youtube_analytics_service: An authenticated YouTube Analytics API service object.
        channel_id: The YouTube channel ID (e.g., UC_x5XG1OV2P6uZZ5FSM9Ttw).
        start_date_str: Start date in YYYY-MM-DD format.
        end_date_str: End date in YYYY-MM-DD format.

    Returns:
        A list of dictionaries, each containing 'month', 'trafficSourceType', and 'views'.
    """
    try:
        response = youtube_analytics_service.reports().query(
            ids=f"channel==MINE",
            startDate=start_date_str,
            endDate=end_date_str,
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

if __name__ == "__main__":
    # Replace with your actual channel ID
    # You can find your channel ID in YouTube Studio -> Settings -> Channel -> Advanced Settings
    # Or by navigating to your channel on YouTube and copying the ID from the URL (e.g., youtube.com/channel/YOUR_CHANNEL_ID)
    YOUR_CHANNEL_ID = "UC1PUNjrDQsFbRqm_fwv-JGg" # <<< IMPORTANT: REPLACE THIS

    # Define the date range
    # Example: Last 6 months
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=180) # Approximately 6 months

    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    start_date_str = '2025-01-01'
    end_date_str = '2025-01-31'

    print(f"Retrieving data for Channel ID: {YOUR_CHANNEL_ID}")
    print(f"From {start_date_str} to {end_date_str}")

    service = get_authenticated_service()

    if service:
        data = get_monthly_views_by_source(service,YOUR_CHANNEL_ID, start_date_str, end_date_str)

        if data:
            print("\nMonthly Views by Traffic Source:")
            '''for entry in data:
                print(f"Source: {entry['source']}, Views: {entry['views']}")'''

            organic=0
            advertising=0
            for source in data:
                if(source['source']== 'ADVERTISING'):
                    advertising += source['views']
                else:
                    organic += source['views']

            print(f"Organic Views: {organic}")
            print(f"Advertising Views: {advertising}")
            print(f"Total Views: {organic + advertising}")

        else:
            print("No data found for the specified period or channel.")