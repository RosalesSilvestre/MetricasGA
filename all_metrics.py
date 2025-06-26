from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.oauth2 import service_account
from datetime import datetime

# 1. Set up authentication
SERVICE_ACCOUNT_FILE = 'secure-air-415716-a1066b9d0ca6.json'  # Download from Google Cloud Console
PROPERTY_ID = '392065347'  # Format: '123456789'
OUTPUT_FILE = 'ga4_fields_report.txt'

# Required scopes
SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']

def save_ga4_fields_to_file():
    """Retrieves all GA4 fields and saves to a formatted text file"""
    # Authentication
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    
    # Initialize client
    client = BetaAnalyticsDataClient(credentials=credentials)
    
    # Get metadata
    metadata = client.get_metadata(name=f"properties/{PROPERTY_ID}/metadata")
    
    # Prepare output content
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = f"""Google Analytics 4 Field Reference
Generated: {timestamp}
Property ID: {PROPERTY_ID}

=== DIMENSIONS ({len(metadata.dimensions)}) ===
{"API Name":<50} | {"UI Name":<30} | {"Category":<15} | Description
{'-'*96}
"""
    
    # Add dimensions
    for dim in metadata.dimensions:
        content += f"{dim.api_name:<50} | {dim.ui_name:<30} | {dim.category:<15} | {dim.description}\n"
    
    content += f"""\n
=== METRICS ({len(metadata.metrics)}) ===
{"API Name":<50} | {"UI Name":<30} | {"Category":<15} | Type        | Description
{'-'*120}
"""
    
    # Add metrics
    for met in metadata.metrics:
        content += f"{met.api_name:<50} | {met.ui_name:<30} | {met.category:<15} | {met.type_:<11} | {met.description}\n"
    
    # Save to file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Successfully saved GA4 field reference to {OUTPUT_FILE}")
    return OUTPUT_FILE

if __name__ == "__main__":
    save_ga4_fields_to_file()