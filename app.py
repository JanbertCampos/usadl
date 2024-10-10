from flask import Flask, request, jsonify
import os
import requests
import re
from huggingface_hub import InferenceClient

app = Flask(__name__)

# Load environment variables
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
HUGGINGFACES_API_KEY = os.environ.get('HUGGINGFACES_API_KEY')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '12345')

# Initialize the Inference client
client = InferenceClient(api_key=HUGGINGFACES_API_KEY)

# Dictionary to hold user contexts
user_context = {}

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Verify the token for the webhook
        if request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        return 'Unauthorized', 403

    # Handle incoming messages
    data = request.get_json()
    handle_message(data)
    return 'OK', 200

def handle_message(data):
    # Assuming data structure contains sender ID and message text
    sender_id = data['entry'][0]['messaging'][0]['sender']['id']
    message_text = data['entry'][0]['messaging'][0].get('message', {}).get('text')

    if message_text:
        # Call your image processing function here
        image_url = extract_image_url(message_text)
        if image_url:
            response = describe_image(image_url)
            send_message(sender_id, response)
        else:
            send_message(sender_id, "No valid image URL found in your message.")

def extract_image_url(message_text):
    # Simple regex to extract URLs from the message text
    url_pattern = r'https?://[^\s]+'
    match = re.search(url_pattern, message_text)
    return match.group(0) if match else None

def describe_image(image_url):
    if not image_url.startswith(('http://', 'https://')):
        return "Invalid image URL."

    try:
        for message in client.chat_completion(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": "Describe this image in one sentence."},
                    ],
                }
            ],
            max_tokens=500,
            stream=False,  # Set to False to get the full response at once
        ):
            return message.choices[0].delta.content
    except Exception as e:
        return f"Error processing image: {str(e)}"

def send_message(recipient_id, message_text):
    url = f'https://graph.facebook.com/v12.0/me/messages?access_token={PAGE_ACCESS_TOKEN}'
    payload = {
        'recipient': {'id': recipient_id},
        'message': {'text': message_text}
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Failed to send message: {str(e)}")

if __name__ == '__main__':
    app.run(port=5000)
