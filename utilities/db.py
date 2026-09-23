import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth

@st.cache_resource
def init_firebase():
    cred = credentials.Certificate("./utilities/adf-check-firebase-adminsdk-s0rox-f5fff88f46.json")
    return firebase_admin.initialize_app(cred)

# Initialize Firebase safely
init_firebase()

# Now use Firestore
db = firestore.client()
