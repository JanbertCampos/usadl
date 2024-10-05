from flask import Flask, request, jsonify
import requests
import os
from huggingface_hub import InferenceClient
import time

app = Flask(__name__)

# Replace with your actual tokens
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
HUGGINGFACES_API_KEY = os.environ.get('HUGGINGFACES_API_KEY')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '12345')

# Dictionary to store user conversations and contexts
user_contexts = {}

# Initialize the Hugging Face API client
client = InferenceClient(api_key=HUGGINGFACES_API_KEY)

@app.route('/webhook', methods=['GET'])
def verify():
    if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN:
        return request.args.get('hub.challenge')
    return 'Invalid verification token', 403

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print(f"Incoming data: {data}")

    if 'messaging' in data['entry'][0]:
        for event in data['entry'][0]['messaging']:
            sender_id = event['sender']['id']
            message_text = event.get('message', {}).get('text')
            image_url = None

            if 'attachments' in event['message']:
                for attachment in event['message']['attachments']:
                    if attachment['type'] == 'image':
                        image_url = attachment['payload']['url']

            # Handle text messages or image attachments
            if message_text:
                print(f"Received message from {sender_id}: {message_text}")
                response_text = get_response_based_on_message(sender_id, message_text, image_url)
                send_message(sender_id, response_text)

    return 'OK', 200

@app.route('/', methods=['GET'])
def home():
    return "Welcome to the webhook service! Use /webhook for messages."

def get_response_based_on_message(sender_id, message_text, image_url):
    context = user_contexts.get(sender_id, {'messages': []})
    context['messages'].append(message_text)

    if image_url:
        return analyze_image(image_url)
    elif "describe this image" in message_text.lower():
        return "Please provide an image for me to describe."
    else:
        return "I didn't quite understand that. Can you please clarify?"

def analyze_image(image_url):
    try:
        response = client.chat_completion(
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
            stream=False,
        )

        if hasattr(response, 'choices') and len(response.choices) > 0:
            return response.choices[0].message['content'].strip()

        return "I'm sorry, I couldn't generate a description for that image."

    except Exception as e:
        print(f"Error analyzing image: {e}")
        return "Sorry, I'm having trouble analyzing that image right now."

def send_message(recipient_id, message_text):
    if recipient_id in user_contexts:  # Check if the user context exists
        payload = {
            'messaging_type': 'RESPONSE',
            'recipient': {'id': recipient_id},
            'message': {'text': message_text}
        }
        response = requests.post(f'https://graph.facebook.com/v12.0/me/messages?access_token={PAGE_ACCESS_TOKEN}', json=payload)
        if response.status_code != 200:
            print(f"Failed to send message: {response.text}")
        else:
            print(f"Message sent successfully to {recipient_id}: {message_text}")
    else:
        print(f"No valid recipient found for user ID: {recipient_id}")

if __name__ == '__main__':
    app.run(port=5000, debug=True)
