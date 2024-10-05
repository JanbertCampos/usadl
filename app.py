from flask import Flask, request
import requests
import os
from huggingface_hub import InferenceClient
import time

app = Flask(__name__)

# Replace with your actual tokens
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
HUGGINGFACES_API_KEY = os.environ.get('HUGGINGFACES_API_KEY')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '12345')

# Instructions for the AI
AI_INSTRUCTIONS = (
    "Your name is JanbertGwapo your girlfriend is aira mariz sorote, a helpful super intelligent in the entire universe and also be polite and kind."
)

# Dictionary to store user conversations and topics
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
            image_url = event.get('message', {}).get('attachments', [{}])[0].get('payload', {}).get('url')

            context = user_contexts.get(sender_id, {'messages': []})
            
            if message_text:
                print(f"Received message from {sender_id}: {message_text}")
                context['messages'].append(message_text)
            elif image_url:
                print(f"Received image from {sender_id}: {image_url}")
                response_text = get_huggingface_image_response(image_url)
                send_message(sender_id, response_text)
                continue

            send_typing_indicator(sender_id)
            response_text = get_huggingface_response(context)
            print(f"Full response: {response_text}")
            send_message(sender_id, response_text)
            user_contexts[sender_id] = context

    return 'OK', 200

def send_message(recipient_id, message_text):
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

def send_typing_indicator(recipient_id):
    payload = {
        'recipient': {'id': recipient_id},
        'sender_action': 'typing_on'
    }
    requests.post(f'https://graph.facebook.com/v12.0/me/messages?access_token={PAGE_ACCESS_TOKEN}', json=payload)
    time.sleep(1)  # Simulate typing delay (optional)

def get_huggingface_response(context):
    user_messages = context['messages'][-10:]
    messages = [{"role": "user", "content": msg} for msg in user_messages]

    try:
        response = client.chat_completion(
            model="meta-llama/Meta-Llama-3-8B-Instruct",
            messages=messages,
            max_tokens=500,
            stream=False
        )
        text = response.choices[0].message['content'] if response.choices else ""
        return text if text else "I'm sorry, I couldn't generate a response. Can you please ask something else?"
    except Exception as e:
        print(f"Error getting response from Hugging Face: {e}")
        return "Sorry, I'm having trouble responding right now."

def get_huggingface_image_response(image_url):
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": "Describe this image in one sentence."},
            ],
        }
    ]

    try:
        response = client.chat_completion(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            messages=messages,
            max_tokens=500,
            stream=False,
        )
        return response.choices[0].message['content'] if response.choices else "I couldn't analyze the image."
    except Exception as e:
        print(f"Error getting image response from Hugging Face: {e}")
        return "Sorry, I couldn't analyze the image."

if __name__ == '__main__':
    app.run(port=5000, debug=True)
