from flask import Flask, render_template, request, jsonify, send_file
from flask_mail import Mail, Message
from google_auth import read_sheet_data, filter_data_by_area, append_to_master_sheet, authenticate_with_oauth, write_to_google_doc
from googleapiclient.discovery import build
import os
import shutil  # For moving files
import csv
from datetime import datetime

app = Flask(__name__)


# Email Configuration
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_USERNAME='kathryn@projectbased.ai',
    MAIL_PASSWORD='jljl zfsy vrsf zdej',
    MAIL_DEFAULT_SENDER=('Signage Briefing App', 'kathryn@projectbased.ai')
)

mail = Mail(app)

#  write_to_google_doc Function
def write_to_google_doc(doc_id, range_name, rows):
    """Mock function to simulate saving to Google Docs."""
    print(f"Mock: Saving to Google Doc ID: {doc_id}, Range: {range_name}, Rows: {len(rows)}")
    # Replace with real Google Docs API logic


# Add your routes and other code below this
#Route to test email
@app.route('/test_email', methods=['GET'])
def test_email():
    """Test email sending functionality."""
    try:
        msg = Message(
            subject="Test Email from Flask",
            recipients=["kathryn@collective.agency"],  # Replace with a test recipient's email
            body="This is a test email sent from your Flask app using Gmail."
        )
        mail.send(msg)
        return "Test email sent successfully!"
    except Exception as e:
        return f"Failed to send email: {e}"


# Route to select an area
@app.route('/', methods=['GET'])
def select_area():
    """Render the Area Selection Page."""
    try:
        return render_template('select_area.html')
    except Exception as e:
        print(f"Error: {e}")
        return f"Error: {e}", 500

# Route to edit signage for a specific area
@app.route('/edit_signage/<area>', methods=['GET'])
def edit_signage(area):
    """Serve the frontend to edit signage for the specified area."""
    try:
        ASSETS_SHEET_ID = '1AZUIWb4ahoZi9LxSVjMpoSdIu1OhD61w6V1BXDVzOhc'
        ASSETS_RANGE_NAME = 'Sheet1!A1:T375'

        assets_data = read_sheet_data(ASSETS_SHEET_ID, ASSETS_RANGE_NAME)
        filtered_assets = [row for row in assets_data if len(row) > 8 and row[8].strip().lower() == area.strip().lower()]

        print(f"Filtered assets for area {area}: {filtered_assets[:3]}")
        return render_template('edit_signage.html', area=area, data=filtered_assets)
    except Exception as e:
        print(f"Error: {e}")
        return f"Error: {e}", 500

# Route to fetch sign types for a given area
@app.route('/get_sign_types/<area>', methods=['GET'])
def get_sign_types(area):
    """Fetch the available sign types for a given area."""
    try:
        LAST_YEAR_SHEET_ID = '1AZUIWb4ahoZi9LxSVjMpoSdIu1OhD61w6V1BXDVzOhc'
        LAST_YEAR_RANGE_NAME = 'Sheet1!A1:T375'
        last_year_data = read_sheet_data(LAST_YEAR_SHEET_ID, LAST_YEAR_RANGE_NAME)

        sign_types = set()
        for row in last_year_data:
            if len(row) > 8 and row[8].strip().lower() == area.strip().lower():
                sign_types.add(row[0].strip().lower())

        return jsonify(sorted(sign_types))
    except Exception as e:
        print(f"Error fetching sign types: {e}")
        return jsonify({"error": "Could not fetch sign types", "details": str(e)}), 500

# Route to process form submissions
@app.route('/submit_signage', methods=['POST'])
def submit_signage():
    """Process edited signage data, assign unique item numbers, append to Master Sheet, and generate a copy."""
    try:
        # Retrieve submitted data as JSON
        if request.content_type == 'application/json':
            submitted_data = request.get_json()  # JSON data
            print(f"Submitted Data (JSON): {submitted_data}")
        else:
            submitted_data = request.form.to_dict(flat=False)  # Form-encoded data
            print(f"Submitted Data (Form): {submitted_data}")

        # Validate and normalize data
        if not submitted_data:
            return jsonify({"success": False, "error": "No data submitted. Please check your form input."}), 400

        if not isinstance(submitted_data, dict):
            return jsonify({"success": False, "error": "Submitted data is not in the correct format."}), 400

        submitted_data = {
            key.upper(): value if isinstance(value, list) else [value]
            for key, value in submitted_data.items()
        }
        print(f"Normalized Data: {submitted_data}")

        # Ensure all fields have consistent lengths
        max_length = max((len(values) for values in submitted_data.values()), default=0)
        for key, values in submitted_data.items():
            if len(values) < max_length:
                submitted_data[key].extend([""] * (max_length - len(values)))

        # Initialize rows for appending to the master sheet
        rows = []
        MASTER_SHEET_ID = '1xIG0vHm1LbPj4kQqD501ewuO9x-bUvGHRg9TuJKZEYU'
        MASTER_RANGE_NAME = 'Sheet1!A2:V1000'

        # Retrieve existing data for unique item numbers
        existing_data = read_sheet_data(MASTER_SHEET_ID, MASTER_RANGE_NAME)
        print(f"Existing Data Retrieved: {len(existing_data)} rows")
        current_index = len(existing_data) + 1

        # Construct rows based on submitted data
        for index in range(len(submitted_data.get('TYPE OF SIGN', []))):
            try:
                row_data = {key: submitted_data.get(key, [""])[index] for key in submitted_data}
                row_data.setdefault('ACTIONS', 'this is a new sign')

                if row_data.get('ACTIONS', '').strip().lower() == 'do not need to create this sign this year'.lower():
                    print(f"Row {index + 1}: Marked for deletion, skipping.")
                    continue

                current_item_number = f"NYM25_{str(current_index).zfill(3)}"
                current_index += 1
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                row = [
                    timestamp,
                    row_data.get('TYPE OF SIGN', ""),
                    row_data.get('PAST ITEM #', ""),
                    current_item_number,
                    row_data.get('BRIEFER', ""),
                    row_data.get('GL CODE', ""),
                    row_data.get('UNIQUE NAME OF ASSET', ""),
                    row_data.get('MANDATORY LOGOS', ""),
                    row_data.get('DESIGN NOTES AND COPY', ""),
                    row_data.get('SIGNAGE DECK PAGE #', ""),
                    row_data.get('AREA', ""),
                    row_data.get('TOTAL QTY FOR RACE', ""),
                    row_data.get('QTY IN INVENTORY', ""),
                    row_data.get('QTY TO PRODUCE', ""),
                    row_data.get('SIDES', ""),
                    row_data.get('MATERIAL', ""),
                    row_data.get('DIMENSIONS (WIDTH - INCHES)', ""),
                    row_data.get('DIMENSIONS (HEIGHT - INCHES)', ""),
                    row_data.get('DIMENSIONS (DEPTH)', ""),
                    row_data.get('FINISHING', ""),
                    row_data.get('DELIVERY ADDRESS', ""),
                    row_data.get('AFTER LIFE', ""),
                    row_data.get('ACTIONS', "")
                ]

                rows.append(row)

            except IndexError as e:
                print(f"Error processing row at index {index}: {e}")
                continue

        print(f"Rows to Append: {rows[:5]}")

        # Append rows to the Master Sheet
        append_to_master_sheet(MASTER_SHEET_ID, MASTER_RANGE_NAME, rows)
        print(f"Appended {len(rows)} rows to the Master Sheet.")

       # Generate the CSV file
        output_file = "submitted_brief.csv"
        with open(output_file, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                "Timestamp", "TYPE OF SIGN", "Past ITEM #", "Current ITEM #", "BRIEFER", "GL CODE",
                "UNIQUE NAME OF ASSET", "MANDATORY LOGOS", "DESIGN NOTES AND COPY",
                "SIGNAGE DECK PAGE #", "AREA", "TOTAL QTY FOR RACE", "QTY IN INVENTORY",
                "QTY TO PRODUCE", "SIDES", "MATERIAL", "DIMENSIONS (WIDTH - INCHES)",
                "DIMENSIONS (HEIGHT - INCHES)", "DIMENSIONS (DEPTH)", "FINISHING",
                "DELIVERY ADDRESS", "AFTER LIFE", "ACTIONS"
            ])
            writer.writerows(rows)
        print(f"CSV Generated at {output_file}")

        # Move the CSV file to the /static directory
        static_folder = os.path.join(os.getcwd(), "static")
        if not os.path.exists(static_folder):
            os.makedirs(static_folder)  # Create the static folder if it doesn't exist
        static_output_file = os.path.join(static_folder, output_file)
        shutil.move(output_file, static_output_file)
        print(f"CSV moved to {static_output_file}")

        # Return JSON response with a link to the CSV
        return jsonify({
            "success": True,
            "message": f"{len(rows)} items have been successfully added to the master sheet.",
            "csv_file": f"/static/{output_file}"
        })

    except Exception as e:
        print(f"Error in submit_signage: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# New route to recommend specifications for a new sign
@app.route('/recommend_specs', methods=['POST'])
def recommend_specs():
    """Recommend specifications for a new sign based on area and type."""
    try:
        user_input = request.json
        area = user_input.get('area', '').strip().lower()
        sign_type = user_input.get('type', '').strip().lower()

        LAST_YEAR_SHEET_ID = '1AZUIWb4ahoZi9LxSVjMpoSdIu1OhD61w6V1BXDVzOhc'
        LAST_YEAR_RANGE_NAME = 'Sheet1!A1:T375'
        last_year_data = read_sheet_data(LAST_YEAR_SHEET_ID, LAST_YEAR_RANGE_NAME)

        dimensions_width = set()
        dimensions_height = set()
        dimensions_depth = set()
        recommended_specs = {
            "Area": area,
            "Sides": None,
            "Material": None,
            "Dimensions_Width": [],
            "Dimensions_Height": [],
            "Dimensions_Depth": [],
            "Finishing": None
        }

        for row in last_year_data:
            if len(row) >= 17:
                row_sign_type = row[0].strip().lower() if row[0] else ""
                row_area = row[8].strip().lower() if row[8] else ""

                if row_sign_type == sign_type and row_area == area:
                    recommended_specs["Sides"] = row[12]
                    recommended_specs["Material"] = row[13]
                    recommended_specs["Finishing"] = row[17]

                    if row[14]:
                        dimensions_width.add(row[14].strip())
                    if row[15]:
                        dimensions_height.add(row[15].strip())
                    if row[16]:
                        dimensions_depth.add(row[16].strip())

        if not dimensions_width:
            return jsonify({"error": "No matching specifications found."}), 404

        recommended_specs["Dimensions_Width"] = sorted(dimensions_width)
        recommended_specs["Dimensions_Height"] = sorted(dimensions_height)
        recommended_specs["Dimensions_Depth"] = sorted(dimensions_depth)

        return jsonify({"recommended_specs": recommended_specs})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Could not fetch recommendations", "details": str(e)}), 500
    

 # Enable users to save their draft before submitting   
# Route to Save Draft

from google_auth import create_draft_sheet, write_to_google_doc  # Import the new function

@app.route('/save_draft', methods=['POST'])
def save_draft():
    """
    Save the current state of the form as a draft and send an email notification.
    """
    try:
        draft_data = request.json
        print(f"Received draft data: {draft_data}")

        briefer_name = draft_data.get('briefer', 'Unnamed Briefer')
        recipient_email = draft_data.get('email', 'default-recipient@example.com')
        print(f"Recipient email: {recipient_email}")

       
        # Create a unique draft sheet for the briefer
        draft_sheet_id = create_draft_sheet(briefer_name)

        # Define the range and data to write
        DRAFT_RANGE_NAME = 'Sheet1!A1:T1000'
        rows = [
            [key] + (value if isinstance(value, list) else [value]) for key, value in draft_data.items()
        ]

        # Write to the briefer's unique draft sheet
        write_to_google_doc(draft_sheet_id, DRAFT_RANGE_NAME, rows)

        # Construct the draft URL
        draft_url = f"https://docs.google.com/spreadsheets/d/{draft_sheet_id}"

        # Send email notification
        recipient_email = draft_data.get('email', 'default-recipient@example.com')
        msg = Message(
            subject="Your Draft Has Been Saved",
            recipients=[recipient_email],
            body=f"""
            Hi {briefer_name},

            Your draft has been successfully saved. You can access it using the link below:
            {draft_url}

            Feel free to continue editing or complete your submission when ready.

            Regards,
            The Signage Briefing Team
            """
        )
        mail.send(msg)

        return jsonify({"success": True, "draft_url": draft_url})
    except Exception as e:
        print(f"Error saving draft: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# Write to the briefer's unique draft sheet
def get_column_letter(n):
    """
    Convert a column index (1-based) to its Excel-style letter representation.

    Args:
        n (int): Column index (1-based, e.g., 1 for 'A', 27 for 'AA').

    Returns:
        str: Column letter.
    """
    result = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result


def write_to_google_doc(sheet_id, range_name, rows):
    """
    Write rows to a specific range in a Google Sheet, dynamically adjusting the range.

    Args:
        sheet_id (str): The ID of the Google Sheet.
        range_name (str): The base range (e.g., 'Sheet1!A1').
        rows (list): A list of lists, where each inner list is a row of data.
    """
    try:
        # Calculate the range dynamically based on the number of columns
        num_columns = max(len(row) for row in rows)  # Get the maximum number of columns in any row
        start_col = 'A'
        end_col = get_column_letter(num_columns)  # Convert column index to letter
        dynamic_range = f"Sheet1!{start_col}1:{end_col}1000"

        # Authenticate using OAuth
        creds = authenticate_with_oauth()
        service = build('sheets', 'v4', credentials=creds)

        # Clear the existing data in the dynamic range
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=dynamic_range
        ).execute()

        # Write the new data
        body = {"values": rows}
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=dynamic_range,
            valueInputOption='RAW',
            body=body
        ).execute()

        print(f"Successfully wrote {len(rows)} rows to Google Sheet ID: {sheet_id}, Range: {dynamic_range}")
    except Exception as e:
        print(f"Error writing to Google Sheet: {e}")
        raise


        # Construct the draft URL
        draft_url = f"https://docs.google.com/spreadsheets/d/{draft_sheet_id}"

        # Send email notification
        recipient_email = draft_data.get('email', 'default-recipient@example.com')
        msg = Message(
            subject="Your Draft Has Been Saved",
            recipients=[recipient_email],
            body=f"""
            Hi {briefer_name},

            Your draft has been successfully saved. You can access it using the link below:
            {draft_url}

            Feel free to continue editing or complete your submission when ready.

            Regards,
            The Signage Briefing Team
            """
        )
        mail.send(msg)

        return jsonify({"success": True, "draft_url": draft_url})
    except Exception as e:
        print(f"Error saving draft: {e}")
        return jsonify({"success": False, "error": str(e)}), 500




if __name__ == "__main__":
    app.run(debug=True)