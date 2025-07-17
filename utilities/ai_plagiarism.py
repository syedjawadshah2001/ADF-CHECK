

import requests

def check_ai_plagiarism(extracted_text: str) -> dict:
    """
    Check if the given text is AI-generated using RapidAPI's AI Content Detector.
    """
    url = "https://ai-content-detector1.p.rapidapi.com/"
    headers = {
        "x-rapidapi-key": "7b0c11e6abmshbb0e8d526465caap12c233jsn239e148c46b2",
        "x-rapidapi-host": "ai-content-detector1.p.rapidapi.com"
    }
    querystring = {"text": extracted_text[:3000]}  # Limit text to avoid API rejection

    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"error": str(e)}
