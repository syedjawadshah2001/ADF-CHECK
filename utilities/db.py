import firebase_admin
from firebase_admin import credentials, firestore, auth

if not firebase_admin._apps:
    cred = credentials.Certificate("./utilities/adf-check-firebase-adminsdk-s0rox-f5fff88f46.json")
    firebase_admin.initialize_app(cred)


db = firestore.client()