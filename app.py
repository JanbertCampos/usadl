from flask import Flask, request
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
        if request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        return 'Unauthorized', 403

    data = request.get_json()
    handle_message(data)
    return 'OK', 200

def handle_message(data):
    messaging_events = data['entry'][0]['messaging']
    for event in messaging_events:
        sender_id = event['sender']['id']
        
        if 'message' in event:
            message = event['message']
            
            if 'attachments' in message:
                for attachment in message['attachments']:
                    if attachment['type'] == 'image':
                        image_url = attachment['payload']['url']
                        response = describe_image(image_url)
                        user_context[sender_id] = response  # Store the description
                        send_message(sender_id, response)
            elif 'text' in message:
                text_query = message['text']
                if sender_id in user_context:
                    # Respond based on previous description
                    send_message(sender_id, handle_query(text_query, user_context[sender_id]))
                else:
                    send_message(sender_id, "Please send an image for analysis.")

def handle_query(query, description):
    if "color" in query.lower():
        # Simple check for colors mentioned in the descriptions
        # You can improve this logic based on your needs
        return "The description does not include specific color details. Please provide the image for color analysis."
    return "I'm not sure how to respond to that."

def describe_image(image_url):
    if not image_url.startswith(('http://', 'https://')):
        return "Invalid image URL."

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

        if response.choices and len(response.choices) > 0:
            return response.choices[0].message['content']
        else:
            return "No description could be generated."

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
