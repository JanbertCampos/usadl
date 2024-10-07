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
    "You are JanbertGwapo, a helpful super intelligent being in the entire universe, and also be polite and kind."
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

    if 'entry' in data and 'messaging' in data['entry'][0]:
        for event in data['entry'][0]['messaging']:
            sender_id = event['sender']['id']
            message_text = event.get('message', {}).get('text')
            message_attachments = event.get('message', {}).get('attachments')

            if message_text:
                print(f"Received message from {sender_id}: {message_text}")
                handle_message(sender_id, message_text)
            elif message_attachments:
                handle_image_message(sender_id, message_attachments)

    return 'OK', 200

def handle_message(sender_id, message_text):
    context = user_contexts.get(sender_id, {'messages': []})
    context['messages'].append(message_text)
    send_typing_indicator(sender_id)
    response_text = get_huggingface_response(context)
    send_message(sender_id, response_text)
    user_contexts[sender_id] = context

def handle_image_message(sender_id, attachments):
    # Assuming the first attachment is the image we want to process
    image_url = attachments[0]['payload']['url']
    print(f"Received image from {sender_id}: {image_url}")

    send_typing_indicator(sender_id)

    response_text = analyze_image(image_url)
    send_message(sender_id, response_text)

def analyze_image(image_url):
    try:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": "Describe this image in one sentence."}
                ]
            }
        ]

        response = client.chat_completion(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            messages=messages,
            max_tokens=500,
            stream=False
        )

        text = response.choices[0].message['content'] if response.choices else ""

        if not text:
            return "I'm sorry, I couldn't analyze the image. Can you please ask something else?"

        return text

    except Exception as e:
        print(f"Error analyzing image: {e}")
        return "Sorry, I'm having trouble analyzing the image right now."

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
    time.sleep(1)

def get_huggingface_response(context):
    user_messages = context['messages'][-10:]
    messages = [{"role": "user", "content": msg} for msg in user_messages]

    try:
        response = client.chat_completion(
            model="meta-llama/Llama-3.2-3B-Instruct",
            messages=messages,
            max_tokens=500,
            stream=False
        )

        text = response.choices[0].message['content'] if response.choices else ""

        if not text:
            return "I'm sorry, I couldn't generate a response. Can you please ask something else?"

        return text
    except Exception as e:
        print(f"Error getting response from Hugging Face: {e}")
        return "Sorry, I'm having trouble responding right now."

if __name__ == '__main__':
    app.run(port=5000, debug=True)