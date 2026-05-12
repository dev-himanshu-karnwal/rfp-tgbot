from google import genai
import asyncio
from google.genai import errors
from config import API_KEY

# Configure API Key
client = genai.Client(api_key=API_KEY)

# async def analyze_rfp(prompt):
    # retries = 3

    # for attempt in range(retries):
    #     try:
    #         response = await asyncio.to_thread(
    #             client.models.generate_content,
    #             model="gemini-2.5-flash",
    #             contents=prompt
    #         )

    #         return response.text

    #     except errors.ServerError as e:
    #         print(f"Retry {attempt + 1}: {e}")

    #         if attempt < retries - 1:
    #             await asyncio.sleep(2)
    #         else:
    #             return "Bot servers are busy. Please try again later."

async def analyze_rfp(prompt):
    try:
        print("Sending prompt to model...")
        stream = client.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=prompt
        )
        response = ""
        for chunk in stream:
            if chunk.text:
                response += chunk.text
                 # send partial response to frontend/websocket here
                print(chunk.text, end="", flush=True)
        return response
    
    except errors.ServerError as e:
        print(f"Error: {e}")
        return "Bot servers are busy. Please try again later."
