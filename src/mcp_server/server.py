from mcp.server.fastmcp import FastMCP
import httpx
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import base64
from common.utils.in_memory_cache import InMemoryCache
from dotenv import load_dotenv

load_dotenv()
mcp = FastMCP("Currency Exchange Rates")

@mcp.tool()
def get_exchange_rate(
    currency_from: str = "USD",
    currency_to: str = "EUR",
    currency_date: str = "latest",
):
    """Use this to get current exchange rate.

    Args:
        currency_from: The currency to convert from (e.g., "USD").
        currency_to: The currency to convert to (e.g., "EUR").
        currency_date: The date for the exchange rate or "latest". Defaults to "latest".

    Returns:
        A dictionary containing the exchange rate data, or an error message if the request fails.
    """
    try:
        response = httpx.get(
            f"https://api.frankfurter.app/{currency_date}",
            params={"from": currency_from, "to": currency_to},
        )
        response.raise_for_status()

        data = response.json()
        if "rates" not in data:
            return {"error": "Invalid API response format."}
        return data
    except httpx.HTTPError as e:
        return {"error": f"API request failed: {e}"}
    except ValueError:
        return {"error": "Invalid JSON response from API."}

# @mcp.tool()
# def generate_image_tool(prompt: str, session_id: str, artifact_file_id = None) -> str:
#   """Image generation tool that generates images or modifies a given image based on a prompt."""

#   if not prompt:
#     raise ValueError("Prompt cannot be empty")

#   client = genai.Client()
#   cache = InMemoryCache()

#   text_input = (
#       prompt,
#       "Ignore any input images if they do not match the request.",
#   )

#   ref_image = None

#   # TODO (rvelicheti) - Change convoluted memory handling logic to a better
#   # version.
#   # Get the image from the cache and send it back to the model.
#   # Assuming the last version of the generated image is applicable.
#   # Convert to PIL Image so the context sent to the LLM is not overloaded
#   try:
#     ref_image_data = None
#     session_image_data = cache.get(session_id)
#     if artifact_file_id:
#       try:
#         ref_image_data = session_image_data[artifact_file_id]
#       except Exception as e:
#         ref_image_data = None
#     if not ref_image_data:
#       # Insertion order is maintained from python 3.7
#       latest_image_key = list(session_image_data.keys())[-1]
#       ref_image_data = session_image_data[latest_image_key]
#     ref_bytes = base64.b64decode(ref_image_data.bytes)
#     ref_image = Image.open(BytesIO(ref_bytes))
#   except Exception as e:
#     ref_image = None

#   if ref_image:
#     contents = [text_input, ref_image]
#   else:
#     contents = text_input
#   try:
#     response = client.models.generate_content(
#         model="gemini-2.0-flash-exp-image-generation",
#         contents=contents,
#         config=types.GenerateContentConfig(response_modalities=["Text", "Image"]),
#     )
#   except Exception as e:
#     print(f"Exception {e}")
#     return -999999999

#   for part in response.candidates[0].content.parts:
#     if part.inline_data is not None:
#       try:
#         data = Imagedata(
#             bytes=base64.b64encode(part.inline_data.data).decode("utf-8"),
#             mime_type=part.inline_data.mime_type,
#             name="generated_image.png",
#             id=uuid4().hex,
#         )
#         session_data = cache.get(session_id)
#         if session_data is None:
#           # Session doesn't exist, create it with the new item
#           cache.set(session_id, {data.id: data})
#         else:
#           # Session exists, update the existing dictionary directly
#           session_data[data.id] = data

#         return data.id
#       except Exception as e:
#         print(f"Exception {e}")
#   return -999999999

if __name__ == "__main__":
    mcp.run(transport="stdio")