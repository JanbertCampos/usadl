from flask import Flask, request, jsonify
import os
from huggingface_hub import InferenceClient

app = Flask(__name__)

# Replace with your actual tokens
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
HUGGINGFACES_API_KEY = os.environ.get('HUGGINGFACES_API_KEY')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '12345')

client = InferenceClient(api_key=HUGGINGFACES_API_KEY)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Verify the webhook
        token = request.args.get('hub.verify_token')
        if token == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        return 'Verification failed', 403

    elif request.method == 'POST':
        data = request.json

        # Process incoming messages
        if 'entry' in data:
            for entry in data['entry']:
                messaging_events = entry.get('messaging', [])
                for event in messaging_events:
                    # Check if the message contains an image URL
                    if 'message' in event and 'attachments' in event['message']:
                        for attachment in event['message']['attachments']:
                            if attachment['type'] == 'image':
                                image_url = attachment['payload']['url']
                                description = get_image_description(image_url)
                                # Here you would send the description back to the user
                                send_message(event['sender']['id'], description)

        return 'OK', 200

def get_image_description(image_url):
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": "Describe this image in one sentence."},
            ],
        }
    ]

    for message in client.chat_completion(
        model="meta-llama/Llama-3.2-11B-Vision-Instruct",
        messages=messages,
        max_tokens=500,
        stream=False,
    ):
        return message.choices[0].delta.content

def send_message(recipient_id, message_text):
    # Function to send a message back to the user
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
