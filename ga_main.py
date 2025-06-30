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

properties = { 'itam.mx': 392120488, 'blog.itam.mx': 392065347}

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

def fetch_metrics(s_d , e_d, prop,metrics_list=[],  dimensions_list=[]):
    '''
    Fetches specified metrics and dimensions from Google Analytics 4.
    
    Args:
        metrics_list (list): List of metric names to fetch.
        dimensions_list (list): List of dimension names to fetch.
        s_d (str): Start date in 'YYYY-MM-DD' format.
        e_d (str): End date in 'YYYY-MM-DD' format.
    '''
    client = BetaAnalyticsDataClient()
    
    metrics = [
        Metric(name=metric) for metric in metrics_list
    ]
    
    dimensions = [
        Dimension(name=dimension) for dimension in dimensions_list
    ]
    date_ranges = [
        DateRange(start_date=s_d, end_date=e_d)
    ]
    
    request = RunReportRequest(
        property=prop,
        metrics=metrics,
        date_ranges=date_ranges,
        dimensions=dimensions
    )
    
    try:
        response = client.run_report(request)
        #print(response)
        # Check if we got data
        result ={}
        if not response.row_count:
            print("No data found for the specified filters and date ranges")
            return
        for row in response.rows:
            for metric_value in row.metric_values:
                metric_name = metrics[row.metric_values.index(metric_value)].name
                if metric_name not in result:
                    result[metric_name] = []
                result[metric_name].append(metric_value.value)
        print(result)
        return response
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    metrics_list = [
        'totalUsers',
        'screenPageViews'
    ]

    dimensions_list = [
        'hostName',
        'week',

    ]

    start_date = "2024-04-01"
    end_date = "2024-04-30"
    for prop in properties:
        print(f"Fetching metrics for property: {prop} ({properties[prop]})")
        prop_cadena = f'properties/{properties[prop]}'
        fetch_metrics(start_date, end_date,prop_cadena, metrics_list)