from flask import Flask, request, jsonify
import os
from huggingface_hub import InferenceClient
import time
import logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Replace with your actual tokens
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
HUGGINGFACES_API_KEY = os.getenv('HUGGINGFACES_API_KEY')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', '12345')

# Initialize the Hugging Face API client
client = InferenceClient(api_key=HUGGINGFACES_API_KEY)

# Dictionary to store user contexts
user_contexts = {}

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.challenge')
    challenge = request.args.get('hub.verify_token')

    if mode and token and challenge:
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            logger.info("Webhook verified successfully")
            return challenge, 200
        else:
            logger.error("Verification failed")
            return '', 403
    else:
        logger.error("Invalid parameters")
        return '', 400

@app.route('/webhook', methods=['POST'])
def handle_incoming_messages():
    data = request.json
    entries = data.get('entry')

    for entry in entries:
        messaging_events = entry.get('messaging')

        for event in messaging_events:
            sender_id = event['sender']['id']
            recipient_id = event['recipient']['id']

            if 'message' in event:
                message_text = event['message'].get('text')
                if message_text:
                    if 'image' in message_text.lower():
                        image_url = extract_image_url(message_text)
                        if image_url:
                            response = describe_image(image_url)
                        else:
                            response = "Please provide a valid image URL."
                    else:
                        response = get_bot_response(message_text, sender_id)

                    send_message(sender_id, recipient_id, response)

    return 'EVENT_RECEIVED', 200

def get_bot_response(message_text, sender_id):
    context = user_contexts.get(sender_id, [])
    context.append({"role": "user", "content": message_text})
    
    try:
        response = client.chat_completion(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            messages=context,
            max_tokens=500,
            stream=False,  # Change to False if you don't want streaming
        )
        user_contexts[sender_id] = context + [{"role": "assistant", "content": response.choices[0].message.content}]
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return "Sorry, I couldn't understand that."

def extract_image_url(message_text):
    # Extract image URL from the message text
    # This is a simple implementation; you may need a more sophisticated parser depending on the format of the message
    start_index = message_text.find('http')
    if start_index != -1:
        end_index = message_text.find(' ', start_index)
        if end_index == -1:
            end_index = len(message_text)
        return message_text[start_index:end_index]
    return None

def describe_image(image_url):
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
                stream=False,  # Change to False if you don't want streaming
        ):
            return message.choices[0].message.content
    except Exception as e:
        logger.error(f"Error describing image: {e}")
        return "Sorry, I couldn't describe that image."

def send_message(recipient_id, sender_id, message_text):
    payload = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(f"https://graph.facebook.com/v13.0/{sender_id}/messages?access_token={PAGE_ACCESS_TOKEN}",
                             json=payload, headers=headers)

    if response.status_code != 200:
        logger.error(f"Failed to send message: {response.text}")

if __name__ == '__main__':
    app.run(port=5000, debug=True)