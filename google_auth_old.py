from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load credentials from JSON file
creds = service_account.Credentials.from_service_account_file('creds.json')

# Build the Google Docs API service
service = build('docs', 'v1', credentials=creds)

# Test: List the user's first 10 Google Docs
results = service.files().list(
    pageSize=10, fields="files(id, name)"
).execute()
items = results.get('files', [])

if not items:
    print("No files found.")
else:
    print("Files:")
    for item in items:
        print(f"{item['name']} ({item['id']})")

