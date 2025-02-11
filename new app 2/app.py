from flask import Flask, redirect, url_for, session, render_template, request, jsonify
import os
import json
import google.auth
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from authlib.integrations.flask_client import OAuth

# ✅ Ensure Flask uses HTTP (Only for Local Dev, Remove for Production)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# ✅ Initialize Flask app
app = Flask(__name__)
app.secret_key = "your_secret_key"  # Change this for security 

# ✅ Step 1: Create `credentials.json` from Environment Variable
CREDENTIALS_PATH = "credentials.json"
credentials_json = os.getenv("GOOGLE_CREDENTIALS")  # Get credentials from Render env

if not credentials_json:
    raise ValueError("⚠️ Error: GOOGLE_CREDENTIALS environment variable is missing.")

# ✅ Write the credentials JSON file
with open(CREDENTIALS_PATH, "w") as file:
    file.write(credentials_json)

# ✅ Google OAuth Config
SCOPES = ["https://www.googleapis.com/auth/drive"]

# ✅ Initialize OAuth flow
flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)

flow = Flow.from_client_secrets_file(
    CREDENTIALS_PATH,
    scopes=SCOPES,
    redirect_uri="http://127.0.0.1:8000/callback"  # FIXED to match your app
)

@app.route("/")
def home():
    if "credentials" not in session:
        return render_template("login.html")  # Show login page
    return redirect(url_for("list_folders"))

@app.route("/login")
def login():
    """Redirect user to Google's OAuth 2.0 login page"""
    authorization_url, state = flow.authorization_url(prompt="consent")
    session["state"] = state  # Store state in session
    return redirect(authorization_url)  # FIXED: Properly redirect

@app.route("/callback")
def callback():
    print("Authorization response URL:", request.url)  # Debugging line

    if "code" not in request.args:
        return "Error: Missing code parameter", 400  # Handle error properly

    # ✅ Fetch token using the authorization response
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session["credentials"] = credentials_to_dict(credentials)  # Store in session

    return redirect(url_for("list_folders"))  # Redirect after login

@app.route("/list-folders")
def list_folders():
    """List user's Google Drive folders"""
    if "credentials" not in session:
        return redirect(url_for("login"))  # Redirect to login
    
    credentials = Credentials(**session["credentials"])
    drive_service = build("drive", "v3", credentials=credentials)

    results = drive_service.files().list(
        q="mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name, webViewLink)"
    ).execute()
    folders = results.get('files', [])
    
    return render_template("folders.html", folders=folders)

def credentials_to_dict(credentials):
    """Convert credentials object to a dictionary for session storage"""
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)  # Fixed port to match your app
