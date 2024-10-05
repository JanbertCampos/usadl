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

# Message templates
MESSAGE_WELCOME = "Welcome! How can I assist you today?"
MESSAGE_ASK_QUESTION = "What would you like to ask?"
MESSAGE_DESCRIBE_IMAGE = "Please send me the image you'd like to describe."
MESSAGE_NO_IMAGE = "I apologize, but I didn't receive any image to analyze. Please share the image first."
MESSAGE_NO_USERS = "It seems I made a mistake! This conversation just started, and we don't have any users yet. Let's start fresh!"

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

            # Check for postback events
            if 'postback' in event:
                postback_payload = event['postback']['payload']
                if postback_payload == "ASK_QUESTION":
                    send_message(sender_id, MESSAGE_ASK_QUESTION)
                elif postback_payload == "DESCRIBE_IMAGE":
                    send_message(sender_id, MESSAGE_DESCRIBE_IMAGE)
                continue  # Skip to the next event

            message_text = event.get('message', {}).get('text')
            attachments = event.get('message', {}).get('attachments', [])

            context = user_contexts.get(sender_id, {'messages': [], 'image_description': None, 'image_url': None})

            # Handle incoming message text
            if message_text:
                message_text = message_text.lower()  # Normalize to lowercase

                if message_text == "get started":
                    send_button_template(sender_id, MESSAGE_WELCOME)
                    continue

                context['messages'].append(message_text)

                send_typing_indicator(sender_id)

                # Process user questions
                response_text = ask_question(message_text)
                send_message(sender_id, response_text)

            # Handle image attachments
            if attachments:
                image_url = attachments[0].get('payload', {}).get('url')
                if image_url:
                    image_response = describe_image(image_url)
                    context['image_description'] = image_response
                    context['image_url'] = image_url
                    send_message(sender_id, image_response)
                else:
                    send_message(sender_id, MESSAGE_NO_IMAGE)

            user_contexts[sender_id] = context

    return 'OK', 200

def extract_error_info(image_description):
    if "error message" in image_description:
        return "The error message indicates a problem with the server configuration. Please check your server logs for more details."
    return "I couldn't find specific error details in the description."

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

def ask_question(user_question):
    try:
        response = client.chat_completion(
            model="meta-llama/Meta-Llama-3-70B-Instruct",
            messages=[{"role": "user", "content": user_question}],
            max_tokens=500,
            stream=False,
        )
        return response.choices[0].message['content'] if response.choices else "I couldn't generate a response."
    except Exception as e:
        print(f"Error asking question: {e}")
        return "Sorry, I'm having trouble answering your question."

def describe_image(image_url):
    try:
        response = client.chat_completion(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            messages=[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_url}}, {"type": "text", "text": "Describe this image in one sentence."}]}],
            max_tokens=500,
            stream=False,
        )
        return response.choices[0].message['content'] if response.choices else "I couldn't analyze the image."
    except Exception as e:
        print(f"Error describing image: {e}")
        return "Sorry, I couldn't analyze the image."

if __name__ == '__main__':
    app.run(port=5000, debug=True)
