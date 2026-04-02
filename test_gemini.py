import os
import sys
sys.path.append("/app")
from google import genai
from google.genai import types

try:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model="gemini-3.1-pro",
        contents="System Instructions:\nYou are a test agent.\n\nUser Request:\nHello. Answer in these sections:\n### Grounded Confidence\nLOW\n\n### Evidence Citations\nNone"
    )
    print(response.text)
except Exception as e:
    import traceback
    traceback.print_exc()
