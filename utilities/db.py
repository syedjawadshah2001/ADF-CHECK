import firebase_admin
from firebase_admin import credentials, firestore, auth

try:
    # Try to get the already initialized app
    firebase_admin.get_app()
except ValueError:
    # If it doesn't exist, initialize it
    cred = credentials.Certificate("./utilities/adf-check-firebase-adminsdk-s0rox-f5fff88f46.json")
    firebase_admin.initialize_app(cred)


db = firestore.client()