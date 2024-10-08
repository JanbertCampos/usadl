from flask import Flask, request
import requests
import os
from huggingface_hub import InferenceClient
import time

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
HUGGINGFACES_API_KEY = os.environ.get('HUGGINGFACES_API_KEY')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '12345')

client = InferenceClient(api_key=HUGGINGFACES_API_KEY)
user_contexts = {}

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
            message_text = event.get('message', {}).get('text', None)
            message_attachments = event.get('message', {}).get('attachments', [])

            context = user_contexts.get(sender_id, {'messages': [], 'mode': None})
            print(f"Current context for {sender_id}: {context}")

            if message_text:
                message_text = message_text.lower().strip()
                handle_user_input(sender_id, message_text, context, message_attachments)

            user_contexts[sender_id] = context

    return 'OK', 200

def handle_user_input(sender_id, message_text, context, message_attachments):
    if message_text == "get started":
        send_message(sender_id, "Please choose an option:\n1. Ask a question\n2. Describe an image")
        context['mode'] = "choose_option"
        context['messages'].append(message_text)

    elif context.get('mode') == "choose_option":
        if message_text == "1":
            context['mode'] = "ask_question"
            send_message(sender_id, "You can now ask your question.")
        elif message_text == "2":
            context['mode'] = "describe_image"
            send_message(sender_id, "Please send an image.")
        else:
            send_message(sender_id, "Invalid option. Please type 'get started' to see options again.")

    elif context.get('mode') == "ask_question":
        context['messages'].append(message_text)
        send_typing_indicator(sender_id)
        response_text = get_huggingface_response(context, question=True)
        send_message(sender_id, response_text)

    elif context.get('mode') == "describe_image":
        if message_attachments:
            handle_image_description(sender_id, message_attachments, context)
        else:
            send_message(sender_id, "I need an image to describe. Please send an image.")

    else:
        send_message(sender_id, "Please type 'get started' to see options.")

def handle_image_description(sender_id, message_attachments, context):
    print(f"Received attachments: {message_attachments}")  # Debugging log
    for attachment in message_attachments:
        if attachment['type'] == 'image':
            image_url = attachment['payload']['url']
            context['messages'].append(image_url)
            print(f"Processing image URL: {image_url}")  # Log the image URL being processed
            send_typing_indicator(sender_id)
            response_text = get_huggingface_response(context, question=False, image_url=image_url)
            send_message(sender_id, response_text)
            return

    send_message(sender_id, "Please send an image.")

def send_message(recipient_id, message_text):
    payload = {
        'messaging_type': 'RESPONSE',
        'recipient': {'id': recipient_id},
        'message': {'text': message_text}
    }
    try:
        response = requests.post(
            f'https://graph.facebook.com/v12.0/me/messages?access_token={PAGE_ACCESS_TOKEN}', 
            json=payload
        )
        
        if response.status_code != 200:
            error_info = response.json().get("error", {})
            print(f"Failed to send message to {recipient_id}: {error_info.get('message')}")
        else:
            print(f"Message sent successfully to {recipient_id}: {message_text}")

    except requests.exceptions.RequestException as e:
        print(f"HTTP Request failed: {e}")

def send_typing_indicator(recipient_id):
    payload = {
        'recipient': {'id': recipient_id},
        'sender_action': 'typing_on'
    }
    try:
        requests.post(f'https://graph.facebook.com/v12.0/me/messages?access_token={PAGE_ACCESS_TOKEN}', json=payload)
        time.sleep(1)  # Simulate typing delay
    except requests.exceptions.RequestException as e:
        print(f"Failed to send typing indicator: {e}")

def get_huggingface_response(context, question=True, image_url=None):
    if question:
        user_messages = context['messages'][-10:]
        messages = [{"role": "user", "content": msg} for msg in user_messages]
        
        response = client.chat_completion(
            model="meta-llama/Llama-3.2-3B-Instruct",
            messages=messages,
            max_tokens=500,
            stream=False
        )
        
        text = response.choices[0].message['content'] if response.choices else ""
        return text or "I'm sorry, I couldn't generate a response."
    
    if image_url:
        messages = [
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": "Please provide a detailed description of this image."}
            ]}
        ]
        
        response = client.chat_completion(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            messages=messages,
            max_tokens=500,
            stream=False,
        )
        
        if response and hasattr(response, 'choices') and len(response.choices) > 0:
            return response.choices[0].message['content'] or "I'm sorry, I couldn't describe the image."
        
        return "I'm sorry, I couldn't describe the image."
    
    return "Invalid request."

if __name__ == '__main__':
    app.run(port=5000, debug=True)