"""Optional AI estimate; formatting never depends on this service."""
import os
import requests

def check_ai_plagiarism(extracted_text: str) -> dict:
    key = os.environ.get("RAPIDAPI_KEY", "")
    if not key:
        return {"error": "AI detection is not configured."}
    try:
        response = requests.get("https://ai-content-detector1.p.rapidapi.com/",
            headers={"x-rapidapi-key": key, "x-rapidapi-host": "ai-content-detector1.p.rapidapi.com"},
            params={"text": extracted_text[:3000]}, timeout=(5, 20))
        response.raise_for_status()
        data = response.json()
        real = float(data.get("real_probability", data.get("human")))
        fake = float(data.get("fake_probability", data.get("ai")))
        if not (0 <= real <= 1 and 0 <= fake <= 1):
            raise ValueError("Invalid probabilities")
        return {"real_probability": real, "fake_probability": fake}
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        return {"error": "The AI service did not return a usable estimate."}
