from flask import Flask, request, jsonify
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os

# Initialize Flask app
app = Flask(__name__)

# Define the scope for the Google Sheets API
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

# OAuth Authentication
def authenticate_with_oauth():
    """Authenticate the user using OAuth 2.0 and request offline access."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('oauth_creds.json', SCOPES)
        creds = flow.run_local_server(port=8080, access_type="offline", prompt="consent")
        with open('token.json', 'w') as token_file:
            token_file.write(creds.to_json())
    return creds

# Authenticate and initialize the Google Sheets API
creds = authenticate_with_oauth()
sheets_service = build('sheets', 'v4', credentials=creds)

# Read Data From a Specific Google Sheet
def read_sheet_data(sheet_id, range_name):
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=range_name
    ).execute()
    rows = result.get('values', [])
    print(f"Retrieved {len(rows)} rows from the sheet.")
    return rows

# Updated filtering function to skip rows with insufficient columns
def filter_data_by_area(data, area):
    """Filter data based on area, ensuring each row has 21 columns."""
    filtered = []
    for row in data:
        if len(row) > 8 and row[8] == area:  # Ensure area column matches
            # Add placeholders for missing columns to make row length 21
            while len(row) < 21:
                row.append("")
            filtered.append(row)
    return filtered


# Combine Assets and Specs
def combine_data(assets, specs):
    """Combine assets and specs into a single list for output."""
    combined = []
    for asset in assets:
        spec = next((s for s in specs if s[0] == asset[0]), None)  # Match by ID (column 0)
        combined.append(asset + (spec if spec else []))
    return combined

# Flask route to process user input and return filtered/combined data
@app.route('/get_signage', methods=['POST'])
def get_signage():
    """Process user input, append data to Master Sheet, and return filtered/combined data."""
    # Get user input (JSON payload)
    user_data = request.json  # Example input: {"area": "Northwest"}
    area = user_data.get('area')

   # Sheet IDs and ranges
    ASSETS_SHEET_ID = '1AZUIWb4ahoZi9LxSVjMpoSdIu1OhD61w6V1BXDVzOhc'
    ASSETS_RANGE_NAME = 'Sheet1!A1:U375'
    SPECS_SHEET_ID = '1Ur7-Q56IYHwLSJkPBl5BIyE_4HQsO4njK1vqu2u44KQ'
    SPECS_RANGE_NAME = 'Sheet1!A2:G44'
    MASTER_SHEET_ID = 'you1xIG0vHm1LbPj4kQqD501ewuO9x-bUvGHRg9TuJKZEYU'  # Replace with the actual Master Sheet ID
    MASTER_RANGE_NAME = 'Sheet1'  # Adjust based on the sheet/tab name


    # Retrieve data
    assets_data = read_sheet_data(ASSETS_SHEET_ID, ASSETS_RANGE_NAME)
    specs_data = read_sheet_data(SPECS_SHEET_ID, SPECS_RANGE_NAME)

    # Filter and combine data
    filtered_assets = filter_data_by_area(assets_data, area)
    filtered_specs = filter_data_by_area(specs_data, area)
    combined_data = combine_data(filtered_assets, filtered_specs)

    # Append combined data to the Master Sheet
    append_to_master_sheet(MASTER_SHEET_ID, MASTER_RANGE_NAME, combined_data)

    # Return combined data as JSON
    return jsonify(combined_data)



def append_to_master_sheet(sheet_id, range_name, data):
    """
    Append rows to a Google Sheet.

    Args:
        sheet_id (str): The ID of the Google Sheet.
        range_name (str): The range where the data will be appended (e.g., 'Sheet1').
        data (list): A list of lists, where each inner list is a row of data.

    Returns:
        dict: The response from the Sheets API.
    """
    body = {
        "values": data
    }

    # Use the Sheets API to append data
    response = sheets_service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=range_name,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body=body
    ).execute()

    print(f"Appended {len(data)} rows to the Master Sheet.")
    return response

# Create a draft sheet for each briefer
def create_draft_sheet(briefer_name):
    """
    Create a new Google Sheet for the briefer's draft and set sharing permissions.

    Args:
        briefer_name (str): Name of the briefer to personalize the sheet.

    Returns:
        str: The ID of the newly created Google Sheet.
    """
    try:
        # Authenticate using OAuth
        creds = authenticate_with_oauth()
        drive_service = build('drive', 'v3', credentials=creds)

        # Metadata for the new sheet
        file_metadata = {
            'name': f'Draft for {briefer_name}',  # Customize the sheet name
            'mimeType': 'application/vnd.google-apps.spreadsheet'
        }

        # Create the sheet
        file = drive_service.files().create(body=file_metadata, fields='id').execute()
        sheet_id = file.get('id')

        # Set file permissions to "Anyone with the link"
        permission = {
            'type': 'anyone',
            'role': 'writer'  # You can use 'reader' if they should only view it
        }
        drive_service.permissions().create(fileId=sheet_id, body=permission).execute()

        print(f"Created draft sheet for {briefer_name}, ID: {sheet_id}")
        return sheet_id
    except Exception as e:
        print(f"Error creating draft sheet: {e}")
        raise


def write_to_google_doc(sheet_id, range_name, rows):
    """Write rows to a specific range in a Google Sheet, overwriting existing data."""
    try:
        # Authenticate using OAuth
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        creds = authenticate_with_oauth()

        # Initialize the Sheets API
        service = build('sheets', 'v4', credentials=creds)

        # Clear the existing data in the range
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()

        # Write the new data
        body = {"values": rows}
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()

        print(f"Successfully wrote {len(rows)} rows to Google Sheet ID: {sheet_id}, Range: {range_name}")
    except Exception as e:
        print(f"Error writing to Google Sheet: {e}")
        raise




# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
