from google import genai
from google.genai import types
import base64
import os


def generate():
    # 1. Point this to the JSON file you downloaded earlier
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "C:/path/to/your/downloaded-key.json"

    # 2. Initialize the client using your project details instead of an API key
    client = genai.Client(
        vertexai=True,
        project="your-gcp-project-id",  # Replace with your actual project ID
        location="us-central1"  # Make sure this matches where you enabled the API
    )

    msg1_text1 = types.Part.from_text(
        text="""A cinematic shot of a Gungan Sith Lord igniting a red lightsaber in the rain, 16:9 aspect ratio. image size = 2k""")

    # You can keep the model name from your snippet
    model = "gemini-3.1-flash-image-preview"

    contents = [
        types.Content(
            role="user",
            parts=[
                msg1_text1
            ]
        ),
    ]

    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        top_p=0.95,
        max_output_tokens=32768,
        response_modalities=["TEXT", "IMAGE"],
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF")
        ],
        image_config=types.ImageConfig(
            aspect_ratio="16:9",  # Set this to match your prompt
            output_mime_type="image/png",
        ),
        # I kept your thinking_config, but if the image model throws an error, delete this block!
        thinking_config=types.ThinkingConfig(
            thinking_level="HIGH",
        ),
    )

    for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
    ):
        print(chunk.text, end="")


generate()