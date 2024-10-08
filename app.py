from flask import Flask, request, jsonify
import os
import requests
from huggingface_hub import InferenceClient

app = Flask(__name__)

# Replace with your actual tokens
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
HUGGINGFACES_API_KEY = os.environ.get('HUGGINGFACES_API_KEY')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '12345')

client = InferenceClient(api_key=HUGGINGFACES_API_KEY)

# In-memory storage for conversation context
user_context = {}

@app.route('/')
def index():
    return "Webhook is running!", 200

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        token = request.args.get('hub.verify_token')
        if token == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        return 'Verification failed', 403

    elif request.method == 'POST':
        data = request.json

        if 'entry' in data:
            for entry in data['entry']:
                messaging_events = entry.get('messaging', [])
                for event in messaging_events:
                    sender_id = event['sender']['id']

                    # Handle image messages
                    if 'message' in event and 'attachments' in event['message']:
                        for attachment in event['message']['attachments']:
                            if attachment['type'] == 'image':
                                image_url = attachment['payload']['url']
                                print(f"Received image URL: {image_url}")
                                description = get_image_description(image_url)
                                store_context(sender_id, "image_description", description)
                                send_message(sender_id, description)

                    # Handle text messages
                    elif 'message' in event and 'text' in event['message']:
                        user_message = event['message']['text']
                        follow_up_response = handle_follow_up(sender_id, user_message)
                        send_message(sender_id, follow_up_response)

        return 'OK', 200

def get_image_description(image_url):
    try:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": "Describe this image in one sentence."},
                ],
            }
        ]

        response = client.chat_completion(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            messages=messages,
            max_tokens=500,
            stream=False,
        )

        if response and hasattr(response, 'choices') and len(response.choices) > 0:
            return response.choices[0].message['content']
        else:
            return "Could not retrieve description."

    except Exception as e:
        print(f"Error retrieving description: {e}")
        return "Could not retrieve description."

def handle_follow_up(sender_id, user_message):
    context = user_context.get(sender_id, {})
    last_description = context.get("image_description")

    if last_description:
        return f"You asked: '{user_message}'. Based on the image description: '{last_description}', what specific details would you like to know more about?"

    return "I don't have any previous context. Could you please clarify your question?"

def store_context(sender_id, key, value):
    if sender_id not in user_context:
        user_context[sender_id] = {}
    user_context[sender_id][key] = value

def send_message(recipient_id, message_text):
    message_data = {
        'recipient': {'id': recipient_id},
        'message': {'text': message_text}
    }

    response = requests.post(
        f'https://graph.facebook.com/v10.0/me/messages?access_token={PAGE_ACCESS_TOKEN}',
        json=message_data
    )

    if response.status_code != 200:
        print(f"Error sending message: {response.text}")

if __name__ == '__main__':
    app.run(port=5000)
