from flask import Flask, request, jsonify
import requests
import os
from huggingface_hub import InferenceClient

app = Flask(__name__)

# Replace with your actual tokens
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
HUGGINGFACES_API_KEY = os.environ.get('HUGGINGFACES_API_KEY')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '12345')

client = InferenceClient(api_key=HUGGINGFACES_API_KEY)

@app.route('/webhook', methods=['GET'])
def webhook_verify():
    if request.args.get('hub.verify_token') == VERIFY_TOKEN:
        return request.args.get('hub.challenge')
    return 'Invalid verification token', 403

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if 'object' in data and data['object'] == 'page':
        for entry in data['entry']:
            for messaging_event in entry['messaging']:
                sender_id = messaging_event['sender']['id']
                if 'message' in messaging_event:
                    if 'attachments' in messaging_event['message']:
                        for attachment in messaging_event['message']['attachments']:
                            if attachment['type'] == 'image':
                                image_url = attachment['payload']['url']
                                description = analyze_image(image_url)
                                send_message(sender_id, description)
    return 'EVENT_RECEIVED', 200

def analyze_image(image_url):
    response_content = ""
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
        stream=False,
    ):
        response_content = message.choices[0].delta.content
    return response_content

def send_message(recipient_id, message_text):
    payload = {
        'recipient': {'id': recipient_id},
        'message': {'text': message_text}
    }
    requests.post(
        f'https://graph.facebook.com/v12.0/me/messages?access_token={PAGE_ACCESS_TOKEN}',
        json=payload
    )

if __name__ == '__main__':
    app.run(port=5000)
