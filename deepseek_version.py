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

# Configuration
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "secure-air-415716-a1066b9d0ca6.json"

properties = { 'itam.mx': 392120488, 'blog.itam.mx': 392065347}

# Parameters
YEAR = 2024

def calculate_dates(year):
    '''
    Calculate start and end dates for the given year. if the year is the current year, it will use the last day of the previous month as the end date.
    if the year is greater than the current year, it will raise an error.
    Returns:
        tuple: (start_date, end_date) in 'YYYY-MM-DD' format.
    '''
    today = datetime.now()
    start_date = f"{year}-01-01"
    if year == today.year:
        end_date = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
    elif year > today.year:
        raise ValueError("Year cannot be greater than the current year.")
    else:
        end_date = f"{year}-12-31"
    return start_date, end_date

def fetch_metrics(s_d , e_d, prop, metrics_list=[], dimensions_list=[]):
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
        result = {}
        if not response.row_count:
            print("No data found for the specified filters and date ranges")
            return None
        for row in response.rows:
            for metric_value in row.metric_values:
                for dimension_value in row.dimension_values:
                    metric_name = metrics[row.metric_values.index(metric_value)].name
                    dimension_value = dimension_value.value
                    if dimension_value not in result:
                        result[dimension_value] = {}
                    #handles when the metric value is a float and needs to be rounded and the casting from string to number
                    data=round(float(metric_value.value), 2)
                    if(data.is_integer()):
                        data = int(data)
                    result[dimension_value][metric_name] = data
        return result
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

def create_excel_report(data, year, filename="analytics_report.xlsx"):
    """
    Creates an Excel report from the analytics data with proper date format for Power BI.
    
    Args:
        data (dict): Dictionary containing analytics data for each property
        year (int): The year of the report
        filename (str): Output Excel filename
    """
    writer = pd.ExcelWriter(filename, engine='xlsxwriter')
    
    for property_name, monthly_data in data.items():
        # Prepare DataFrame
        rows = []
        for month_num, metrics in monthly_data.items():
            # Calculate the last day of the month
            if int(month_num) == 12:
                last_day = datetime(year, 12, 31)
            else:
                last_day = datetime(year, int(month_num)+1, 1) - timedelta(days=1)
            
            rows.append({
                'Date': last_day.strftime('%Y-%m-%d'),  # Format as YYYY-MM-DD for Power BI
                'Total Users': metrics.get('totalUsers', 0),
                'Total Views': metrics.get('screenPageViews', 0)
            })
        
        # Create DataFrame and sort by date
        df = pd.DataFrame(rows)
        #df['Date'] = pd.to_datetime(df['Date'])  # Convert to datetime for proper sorting
        df = df.sort_values('Date')
        
        # Write to Excel
        df.to_excel(writer, sheet_name=property_name[:31], index=False)  # Sheet name max 31 chars
        
        # Get workbook and worksheet objects for formatting
        workbook = writer.book
        worksheet = writer.sheets[property_name[:31]]
        
        # Add some formatting
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })
        
        # Date format for Power BI compatibility
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
        
        # Write the column headers with the defined format
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Apply date format to date column
        worksheet.set_column('A:A', 15, date_format)  # Date column
        worksheet.set_column('B:C', 15)  # Metric columns
    
    # Save the Excel file
    writer.close()
    print(f"Excel report generated: {filename}")

if __name__ == "__main__":
    metrics_list = [
        'totalUsers',
        'screenPageViews',
        'screenPageViewsPerSession'
    ]

    dimensions_list = [
        'month'
    ]

    try:
        start_date, end_date = calculate_dates(YEAR)
    except ValueError as e:
        print(f"Error: {str(e)}")
        exit(1)
    
    all_data = {}
    
    for prop in properties:
        print(f"Fetching metrics for property: {prop} ({properties[prop]})")
        prop_cadena = f'properties/{properties[prop]}'
        result = fetch_metrics(start_date, end_date, prop_cadena, metrics_list, dimensions_list)
        
        if result:
            # Sort the result by month
            result = dict(sorted(result.items()))
            all_data[prop] = result
            
            print(f"Results for {prop} {YEAR}:")
            for month_num, metrics in result.items():
                print(f"Month {month_num}: {metrics}")
        else:
            print(f"No data found for property: {prop}")
    
    # Create Excel report if we have data
    if all_data:
        create_excel_report(all_data, YEAR, filename=f"analytics_report_{YEAR}.xlsx")
    else:
        print("No data available to generate Excel report")