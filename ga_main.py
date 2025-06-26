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

# Configuration
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "secure-air-415716-a1066b9d0ca6.json"
PROPERTY_ID = "properties/392120488"


def create_host_filter():
    # Create URL path filter
    url_filter = FilterExpression(
        filter=Filter(
            field_name="pagePath",
            string_filter=Filter.StringFilter(
                match_type=Filter.StringFilter.MatchType.FULL_REGEXP,
                value=r"\/\d{4}\/(0[1-9]|1[0-2])\/(0[1-9]|[12]\d|3[01])\/.*"
            )
        )
    )
    
    # Combine with host filter if needed
    host_filter = FilterExpression(
        filter=Filter(
            field_name="hostName",
            string_filter=Filter.StringFilter(
                match_type=Filter.StringFilter.MatchType.ENDS_WITH,
                value="mundoitam.com"
            )
        )
    )
    # Create filter to exclude internal traffic
    '''internal_traffic_filter = FilterExpression(
        filter=Filter(
            field_name="isInternalTraffic",
            string_filter=Filter.StringFilter(
                match_type=Filter.StringFilter.MatchType.EXACT,
                value="false"  # "true" for internal traffic, "false" for external
            )
        )
    )'''
    
    # Combine filters with AND logic
    return FilterExpression(
        and_group={
            "expressions": [url_filter, host_filter]
        }
    )

def fetch_metrics():
    client = BetaAnalyticsDataClient()
    
    metrics = [
        Metric(name="activeUsers"),
        Metric(name="screenPageViews")
    ]
    
    dimensions = [
        Dimension(name="sessionSource")
    ]
    date_ranges = [
        DateRange(start_date="2024-04-01", end_date="2024-04-30")
    ]
    
    request = RunReportRequest(
        property=PROPERTY_ID,
        metrics=metrics,
        date_ranges=date_ranges,
        dimensions=dimensions,
        #dimension_filter=create_host_filter(),
        metric_aggregations=["TOTAL"],
    )
    
    try:
        response = client.run_report(request)

        #print(response)
        
        # Check if we got data
        if not response.row_count:
            print("No data found for the specified filters and date ranges")
            return
        sum=0
        for i in range (len(response.rows)):
            source_name = response.rows[i].dimension_values[0].value
            users = response.rows[i].metric_values[1].value
            sum+= int(users)
            print(source_name)
            print(users)
            
        print(f"Total users from non-Google sources: {sum}")
    except Exception as e:
        print(f"Error: {str(e)}")

def list_all_hostnames():
    client = BetaAnalyticsDataClient()
    
    request = RunReportRequest(
        property=PROPERTY_ID,
        dimensions=[Dimension(name="sessionSource")],
        date_ranges=[DateRange(start_date="2025-04-01", end_date="2025-04-30")],
        #dimension_filter=create_host_filter(),  # Filter to only show .itam.mx hosts
        limit=50
    )
    
    try:
        response = client.run_report(request)
        
        print("\nHostnames ending with .itam.mx:")
        print("-----------------------------")
        if response.row_count == 0:
            print("No matching hosts found")
        else:
            for row in response.rows:
                for dimension in row.dimension_values:
                    print(dimension.value)
    except Exception as e:
        print(f"Error listing hostnames: {str(e)}")

if __name__ == "__main__":
    fetch_metrics()
    #list_all_hostnames()