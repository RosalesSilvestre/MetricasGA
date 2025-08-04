import os
import datetime
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    Filter,
    FilterExpression,
    FilterExpressionList
)
import os
import pandas as pd
from datetime import datetime, timedelta

from youtube_main import get_authenticated_service

def fetch_google_analytics_data(StartDate, EndDate):
    """Fetches data from Google Analytics for the specified properties and date range."""
    # Configuration
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "secure-air-415716-a1066b9d0ca6.json"
    properties = { 'itam.mx': 392120488, 'blog.itam.mx': 392065347}

    # Creates a client for the Google Analytics Data API
    client = BetaAnalyticsDataClient()
    
    #Defines the metrics and dimensions to fetch
    metrics_list = ["activeUsers", "totalUsers"]
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
                "activeUsers": [row.metric_values[0].value for row in response_itam.rows],
                "totalUsers": [row.metric_values[1].value for row in response_itam.rows],
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
                "activeUsers": [row.metric_values[0].value for row in response_blog.rows],
                "totalUsers": [row.metric_values[1].value for row in response_blog.rows],
            }

    except Exception as e:
        print(f"Error fetching data for blog.itam.mx: {e}")
        response_blog = None

    return results

def fetch_youtube_analytics_data(channel_id, start_date, end_date):
    """Fetches data from YouTube Analytics for the specified channel and date range."""
    youtube_analytics_service = get_authenticated_service()
    # Define the request
    request = youtube_analytics_service.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start_date,
        endDate=end_date,
        metrics="views,likes,subscribersGained",
        dimensions="day"
    )
    # Make the request
    response = request.execute()
    return response

def main(StartDate, EndDate):
    """Main function to execute the script.
    It gets the metrics from Google Analytics, then from YouTube Analytics, and finally from Report Files
    
    and saves the results to a CSV file."""
    # Fetch Google Analytics data
    google_analytics_data = fetch_google_analytics_data(StartDate, EndDate)

    print("Google Analytics Data:")
    for property_name, data in google_analytics_data.items():
        print(f"{property_name}:")
        print(f"  Active Users: {data.get('activeUsers', 'No data')}")
        print(f"  Total Users: {data.get('totalUsers', 'No data')}")

if __name__ == "__main__":
    main('2025-01-01', '2025-01-31')
    