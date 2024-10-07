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
AI_INSTRUCTIONS = "You are JanbertGwapo, a helpful super intelligent being in the universe and also be polite and kind."

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

    if 'entry' in data and len(data['entry']) > 0 and 'messaging' in data['entry'][0]:
        for event in data['entry'][0]['messaging']:
            sender_id = event['sender']['id']
            message_text = event.get('message', {}).get('text')

            if message_text:
                print(f"Received message from {sender_id}: {message_text}")

                context = user_contexts.get(sender_id, {'messages': [], 'mode': None})
                
                # Handle "get started" command
                if message_text.lower() == "get started":
                    send_message(sender_id, "Please choose an option:\n1. Ask a question\n2. Describe an image")
                    context['mode'] = "choose_option"
                elif context.get('mode') == "choose_option":
                    if message_text.strip() == "1":
                        context['mode'] = "ask_question"
                        send_message(sender_id, "You can now ask your question.")
                    elif message_text.strip() == "2":
                        context['mode'] = "describe_image"
                        send_message(sender_id, "Please provide the image URL.")
                    else:
                        send_message(sender_id, "Invalid option. Please type 'get started' to see options again.")
                elif context['mode'] == "ask_question":
                    context['messages'].append(message_text)
                    send_typing_indicator(sender_id)
                    response_text = get_huggingface_response(context, question=True)
                    send_message(sender_id, response_text)
                elif context['mode'] == "describe_image":
                    # Assume the user sends an image URL
                    if is_valid_image_url(message_text):
                        context['messages'].append(message_text)
                        send_typing_indicator(sender_id)
                        response_text = get_huggingface_response(context, question=False, image_url=message_text)
                        send_message(sender_id, response_text)
                    else:
                        send_message(sender_id, "Please provide a valid image URL.")
                else:
                    send_message(sender_id, "Please type 'get started' to see options.")

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
    time.sleep(1)

def get_huggingface_response(context, question=True, image_url=None):
    if question:
        user_messages = context['messages'][-10:]  # Get the last N messages
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
                {"type": "text", "text": "Describe this image in one sentence."}
            ]}
        ]
        
        response = client.chat_completion(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            messages=messages,
            max_tokens=500,
            stream=True,
        )
        
        text = ""
        for message in response:
            text += message.choices[0].delta.content
        return text or "I'm sorry, I couldn't describe the image."
    
    return "Invalid request."

def is_valid_image_url(url):
    # Implement your logic to validate the URL, e.g., check if it ends with an image format
    return url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))

if __name__ == '__main__':
    app.run(port=5000, debug=True)
