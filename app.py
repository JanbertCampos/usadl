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
            attachments = event.get('message', {}).get('attachments', [])
            image_url = attachments[0].get('payload', {}).get('url') if attachments else None

            context = user_contexts.get(sender_id, {'messages': []})

            # Handle postback buttons
            if 'postback' in event.get('message', {}):
                payload = event['message']['postback']['payload']
                if payload == "DESCRIBE_IMAGE":
                    send_message(sender_id, "Please send me the image you'd like to describe.")
                    continue

            if message_text:
                print(f"Received message from {sender_id}: {message_text}")
                context['messages'].append(message_text)

                send_typing_indicator(sender_id)

                # Check for "Get Started" message
                if message_text.strip().lower() == "get started":
                    send_button_template(sender_id, "Welcome! How can I assist you today?")
                elif "error in image" in message_text.lower():
                    if image_url:
                        send_message(sender_id, "I have received the image. Please provide details about the error you are encountering.")
                    else:
                        send_message(sender_id, "I apologize, but I didn't receive any image to analyze. Please share the image first, and then describe the issue you're experiencing.")
                else:
                    # Get the response from Hugging Face model
                    response_text = get_huggingface_response(context)
                    send_button_template(sender_id, response_text)

            if image_url:
                print(f"Received image from {sender_id}: {image_url}")
                image_response = get_huggingface_image_response(image_url)
                send_button_template(sender_id, image_response)

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
        error_message = response.json().get('error', {}).get('message', 'Unknown error occurred.')
        print(f"Failed to send message: {error_message}")
        
        if "No matching user found" in error_message:
            print("This user has not interacted with the bot recently; cannot send message.")
    else:
        print(f"Message sent successfully to {recipient_id}: {message_text}")

def send_button_template(recipient_id, message_text):
    payload = {
        'messaging_type': 'RESPONSE',
        'recipient': {'id': recipient_id},
        'message': {
            'attachment': {
                'type': 'template',
                'payload': {
                    'template_type': 'button',
                    'text': message_text,
                    'buttons': [
                        {
                            "type": "postback",
                            "title": "Ask a Question",
                            "payload": "ASK_QUESTION"
                        },
                        {
                            "type": "postback",
                            "title": "Describing an Image",
                            "payload": "DESCRIBE_IMAGE"
                        }
                    ]
                }
            }
        }
    }
    requests.post(f'https://graph.facebook.com/v12.0/me/messages?access_token={PAGE_ACCESS_TOKEN}', json=payload)

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