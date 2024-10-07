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

    if 'entry' in data and 'messaging' in data['entry'][0]:
        for event in data['entry'][0]['messaging']:
            sender_id = event['sender']['id']
            message_text = event.get('message', {}).get('text')
            message_attachments = event.get('message', {}).get('attachments')

            # Check if the user typed "Get Started"
            if message_text and message_text.lower() == "get started":
                send_options(sender_id)
                continue

            if message_text:
                print(f"Received message from {sender_id}: {message_text}")
                handle_text_message(sender_id, message_text)
            elif message_attachments:
                handle_image_message(sender_id, message_attachments)

    return 'OK', 200

def send_options(recipient_id):
    buttons = [
        {
            "type": "postback",
            "title": "Ask a question",
            "payload": "ASK_QUESTION"
        },
        {
            "type": "postback",
            "title": "Describe an image",
            "payload": "DESCRIBE_IMAGE"
        }
    ]

    options_message = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": "Welcome! Please choose an option:",
                "buttons": buttons
            }
        }
    }

    send_message(recipient_id, options_message)

def handle_text_message(sender_id, message_text):
    context = user_contexts.get(sender_id, {'messages': [], 'mode': 'question', 'image_url': None})

    # Check if the user is choosing a mode based on the buttons
    if message_text.lower() == "ask a question":
        context['mode'] = 'question'
        send_message(sender_id, "You can now ask your question.")
    elif message_text.lower() == "describe an image":
        context['mode'] = 'describe'
        send_message(sender_id, "Please upload an image to describe.")
    else:
        # Handle regular messages based on current mode
        if context['mode'] == 'question':
            response_text = get_huggingface_response(context, message_text)
            send_message(sender_id, response_text)
        elif context['mode'] == 'describe' and context['image_url']:
            response_text = get_huggingface_response(context)
            send_message(sender_id, response_text)
        else:
            send_message(sender_id, "Please select 'Ask a question' or 'Describe an image'.")

    # Update context with the new message
    context['messages'].append(message_text)
    user_contexts[sender_id] = context

def handle_image_message(sender_id, attachments):
    image_url = attachments[0]['payload']['url']
    print(f"Received image from {sender_id}: {image_url}")

    send_typing_indicator(sender_id)

    response_text = analyze_image(image_url)

    # Update context with the image URL and switch to 'describe' mode
    context = user_contexts.get(sender_id, {'messages': [], 'mode': 'describe', 'image_url': None})
    context['messages'].append(response_text)  # Add the image description to context
    context['image_url'] = image_url  # Store the image URL
    context['mode'] = 'describe'  # Set mode to describe

    user_contexts[sender_id] = context  # Store updated context
    send_message(sender_id, response_text)

def analyze_image(image_url):
    try:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": "Describe this image in one sentence."}
                ]
            }
        ]

        response = client.chat_completion(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            messages=messages,
            max_tokens=500,
            stream=False
        )

        text = response.choices[0].message['content'] if response.choices else ""

        if not text:
            return "I'm sorry, I couldn't analyze the image. Can you please ask something else?"

        return text

    except Exception as e:
        print(f"Error analyzing image: {e}")
        return "Sorry, I'm having trouble analyzing the image right now."

def send_message(recipient_id, message_text):
    payload = {
        'messaging_type': 'RESPONSE',
        'recipient': {'id': recipient_id},
        'message': message_text if isinstance(message_text, dict) else {'text': message_text}
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

def get_huggingface_response(context, user_question=None):
    user_messages = context['messages'][-10:]  # Get the last 10 messages
    if user_question:
        user_messages.append(user_question)  # Append the current question
    messages = [{"role": "user", "content": msg} for msg in user_messages]

    print(f"Sending messages to Hugging Face: {messages}")  # Debug statement

    try:
        response = client.chat_completion(
            model="meta-llama/Llama-3.2-3B-Instruct",
            messages=messages,
            max_tokens=500,
            stream=False
        )

        text = response.choices[0].message['content'] if response.choices else ""
        print(f"Response from Hugging Face: {text}")  # Debug statement

        if not text:
            return "I'm sorry, I couldn't generate a response. Can you please ask something else?"

        return text
    except Exception as e:
        print(f"Error getting response from Hugging Face: {e}")
        return "Sorry, I'm having trouble responding right now."

def handle_database_errors(sender_id):
    error_options = [
        "Database connection issue",
        "SQL syntax error",
        "Data type mismatch error",
        "Constraint violation error",
        "Transactions rolled back",
        "Indexing error",
        "Query timeout error",
        "Data integrity error"
    ]

    options_message = "Here are some possible database errors you might encounter:\n" + "\n".join(f"{i+1}. {error}" for i, error in enumerate(error_options))
    options_message += "\nPlease type the error name or select a number to learn more about it."
    send_message(sender_id, options_message)

if __name__ == '__main__':
    app.run(port=5000, debug=True)
