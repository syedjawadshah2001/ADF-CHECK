

import requests

def check_ai_plagiarism(extracted_text: str) -> dict:
    """
    Check if the given text is AI-generated using RapidAPI's AI Content Detector.
    """
    url = "https://ai-content-detector1.p.rapidapi.com/"
    headers = {
        "x-rapidapi-key": "95ed1f0ccfmsh5b7b5a6338e2b35p1eb87djsnafe4b524dc3c",
        "x-rapidapi-host": "ai-content-detector1.p.rapidapi.com"
    }
    querystring = {"text": extracted_text[:3000]}  # Limit text to avoid API rejection

    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"error": str(e)}
