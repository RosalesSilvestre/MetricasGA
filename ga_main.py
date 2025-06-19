from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
import os

# Replace these values with your actual GA4 property ID
# Format: properties/123456789 (find in GA4 admin)
PROPERTY_ID = "properties/392065347"

# Path to your service account JSON file
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "secure-air-415716-a1066b9d0ca6.json"

def sample_run_report():
    """Runs a simple report on a Google Analytics 4 property."""
    # Initialize client
    client = BetaAnalyticsDataClient()

    # Create the request
    request = RunReportRequest(
        property=PROPERTY_ID,
        dimensions=[Dimension(name="country")],
        metrics=[Metric(name="activeUsers")],
        date_ranges=[DateRange(start_date="7daysAgo", end_date="today")],
    )

    # Make the request
    response = client.run_report(request)

    print("Report result:")
    print(f"{'Country':<20} {'Active Users':>15}")
    print("-" * 35)
    
    for row in response.rows:
        country = row.dimension_values[0].value
        users = row.metric_values[0].value
        print(f"{country:<20} {users:>15}")

if __name__ == "__main__":
    sample_run_report()