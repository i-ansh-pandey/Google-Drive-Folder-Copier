from flask import Flask, redirect, url_for, session, render_template, request, jsonify
import os
import google.auth
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "secret_key"  # Change this for security 

# Google OAuth Config
CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/drive"]

# OAuth flow
flow = Flow.from_client_secrets_file(
    CLIENT_SECRETS_FILE,
    scopes=SCOPES,
    redirect_uri="http://127.0.0.1:5000/callback"
)

@app.route("/")
def home():
    if "credentials" not in session:
        return render_template("login.html")  # Show login page
    return redirect(url_for("list_folders"))
    return "Google Drive Folder Copier is running!"


@app.route("/login")
def login():
    """Redirect user to Google's OAuth 2.0 login page"""
    authorization_url, state = flow.authorization_url(prompt="consent")
    session["state"] = state  # Store state in session
    return render_template("login.html")
    return redirect(authorization_url)

@app.route("/callback")
def callback():
    print("Authorization response URL:", request.url)  # Debugging line

    if "code" not in request.args:
        return "Error: Missing code parameter", 400  # Handle error properly

    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session["credentials"] = credentials_to_dict(credentials)

    return redirect(url_for("list_folders"))  # Redirect after login

@app.route("/list-folders")
def list_folders():
    """List user's Google Drive folders"""
    if "credentials" not in session:
        return render_template("login.html")  # Redirect user to login
    
    credentials = Credentials(**session["credentials"])
    drive_service = build("drive", "v3", credentials=credentials)

    results = drive_service.files().list(
        q="mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name, webViewLink)"
    ).execute()
    folders = results.get('files', [])
    
    return render_template("folders.html", folders=folders)


def credentials_to_dict(credentials):
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }

@app.route("/copy-folder/<folder_id>", methods=["POST"])
def copy_folder(folder_id):
    """Copy a Google Drive folder and its contents"""
    try:
        credentials = Credentials(**session["credentials"])
        drive_service = build("drive", "v3", credentials=credentials)

        # Get folder name
        folder = drive_service.files().get(fileId=folder_id, fields="name").execute()
        new_folder_metadata = {
            "name": folder["name"] + " - Copy",
            "mimeType": "application/vnd.google-apps.folder",
            "parents": ["root"]  # Change this to another folder ID if needed
        }
        new_folder = drive_service.files().create(body=new_folder_metadata, fields="id").execute()
        new_folder_id = new_folder["id"]

        # Get all files and subfolders in the original folder
        results = drive_service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id, name, mimeType)"
        ).execute()
        items = results.get("files", [])

        # Copy each file or folder
        for item in items:
            if item["mimeType"] == "application/vnd.google-apps.folder":
                copy_subfolder(drive_service, item["id"], new_folder_id)
            else:
                copy_file(drive_service, item["id"], item["name"], new_folder_id)

        return jsonify({"message": "Folder copied successfully!", "new_folder_id": new_folder_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def copy_file(drive_service, file_id, file_name, new_parent_id):
    """Copy a single file to a new parent folder"""
    file_metadata = {
        "name": file_name,
        "parents": [new_parent_id]
    }
    drive_service.files().copy(fileId=file_id, body=file_metadata).execute()

def copy_subfolder(drive_service, old_folder_id, new_parent_id):
    """Recursively copy a folder and its contents"""
    old_folder = drive_service.files().get(fileId=old_folder_id, fields="name").execute()
    new_folder_metadata = {
        "name": old_folder["name"],
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [new_parent_id]
    }
    new_folder = drive_service.files().create(body=new_folder_metadata, fields="id").execute()
    new_folder_id = new_folder["id"]

    # Get contents of old folder
    results = drive_service.files().list(
        q=f"'{old_folder_id}' in parents and trashed=false",
        fields="files(id, name, mimeType)"
    ).execute()
    items = results.get("files", [])

    # Copy each file or subfolder
    for item in items:
        if item["mimeType"] == "application/vnd.google-apps.folder":
            copy_subfolder(drive_service, item["id"], new_folder_id)
        else:
            copy_file(drive_service, item["id"], item["name"], new_folder_id)

if __name__ == "__main__":
    app.run(debug=True)
