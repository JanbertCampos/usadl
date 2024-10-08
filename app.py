from flask import Flask, request
import requests
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
def verify():
    """Verification for the webhook."""
    mode = request.args.get('hub.mode')
    verify_token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode == 'subscribe' and verify_token == VERIFY_TOKEN:
        logger.info(f"Verification successful for challenge: {challenge}")
        return challenge
    logger.error("Invalid verification token")
    return 'Invalid verification token', 403

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming messages from users."""
    try:
        data = request.get_json()
        logger.debug(f"Incoming data: {data}")

        if 'entry' in data and 'messaging' in data['entry'][0]:
            for event in data['entry'][0]['messaging']:
                sender_id = event['sender']['id']
                message_text = event.get('message', {}).get('text', None)
                message_attachments = event.get('message', {}).get('attachments', [])

                # Initialize or retrieve user context
                context = user_contexts.get(sender_id, {'messages': [], 'mode': None})
                logger.debug(f"Current context for {sender_id}: {context}")

                # Handle user commands based on context
                if message_text:
                    message_text = message_text.lower().strip()
                    handle_user_input(sender_id, message_text, context, message_attachments)

                user_contexts[sender_id] = context  # Update user context

        return 'OK', 200
    except Exception as e:
        logger.error(f"Error handling webhook: {e}", exc_info=True)
        return str(e), 500

def handle_user_input(sender_id, message_text, context, message_attachments):
    """Process user input based on the current context."""
    if message_text == "get started":
        send_message(sender_id, "Please choose an option:\n1. Ask a question\n2. Describe an image")
        context['mode'] = "choose_option"
        context['messages'].append(message_text)  # Store user command

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
    """Process image attachments and get their descriptions."""
    for attachment in message_attachments:
        if attachment['type'] == 'image':
            image_url = attachment['payload']['url']
            context['messages'].append(image_url)  # Store the image URL
            send_typing_indicator(sender_id)
            response_text = get_huggingface_response(context, question=False, image_url=image_url)
            send_message(sender_id, response_text)
            return  # Exit after processing the first image

    send_message(sender_id, "Please send an image.")

def send_message(recipient_id, message_text, retries=3):
    """Send a message to the user with a retry mechanism."""
    payload = {
        'messaging_type': 'RESPONSE',
        'recipient': {'id': recipient_id},
        'message': {'text': message_text}
    }
    for attempt in range(retries):
        try:
            response = requests.post(
                f'https://graph.facebook.com/v12.0/me/messages?access_token={PAGE_ACCESS_TOKEN}', 
                json=payload
            )
            
            if response.status_code != 200:
                error_info = response.json().get("error", {})
                logger.error(f"Attempt {attempt+1} failed to send message to {recipient_id}: {error_info.get('message')}")
            else:
                logger.info(f"Message sent successfully to {recipient_id}: {message_text}")
                return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Attempt {attempt+1} HTTP Request failed: {e}")
    
    logger.error(f"Failed to send message to {recipient_id} after {retries} attempts")
    return False

def send_typing_indicator(recipient_id):
    """Send a typing indicator to the user."""
    payload = {
        'recipient': {'id': recipient_id},
        'sender_action': 'typing_on'
    }
    try:
        requests.post(f'https://graph.facebook.com/v12.0/me/messages?access_token={PAGE_ACCESS_TOKEN}', json=payload)
        time.sleep(1)  # Simulate typing delay
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send typing indicator: {e}")

def get_huggingface_response(context, question=True, image_url=None):
    """Get response from Hugging Face model based on user input."""
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