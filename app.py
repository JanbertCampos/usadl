from flask import Flask, request
import requests
import os
from huggingface_hub import InferenceClient

app = Flask(__name__)

# Replace with your actual tokens
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
HUGGINGFACES_API_KEY = os.environ.get('HUGGINGFACES_API_KEY')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '12345')

# Initialize the Hugging Face API client
client = InferenceClient(api_key=HUGGINGFACES_API_KEY)

# Dictionary to store user conversations and topics
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

    if 'messaging' in data['entry'][0]:
        for event in data['entry'][0]['messaging']:
            sender_id = event['sender']['id']
            message_text = event.get('message', {}).get('text')
            attachments = event.get('message', {}).get('attachments', [])

            # Retrieve or initialize the conversation context
            context = user_contexts.get(sender_id, {'messages': []})

            if message_text:
                print(f"Received message from {sender_id}: {message_text}")
                context['messages'].append(message_text)  # Add text message to context

                # Handle "Get Started" command
                if "get started" in message_text.lower():
                    send_gallery_options(sender_id)

                elif "ask a question" in message_text.lower():
                    send_message(sender_id, "What is your question?")

                elif "describe image" in message_text.lower():
                    send_message(sender_id, "Please send an image for me to describe.")

                elif attachments:
                    image_url = None
                    for attachment in attachments:
                        if attachment['type'] == 'image':
                            image_url = attachment['payload']['url']
                            break

                    if image_url:
                        response_text = get_huggingface_image_response(image_url)
                        send_message(sender_id, response_text)
                    else:
                        send_message(sender_id, "I didn't receive a valid image. Please try again.")

                elif "what is" in message_text.lower():
                    response_text = get_huggingface_question_response(message_text)
                    send_message(sender_id, response_text)

                else:
                    send_message(sender_id, "I can only respond to specific commands.")

            user_contexts[sender_id] = context

    return 'OK', 200

def send_gallery_options(recipient_id):
    options = [
        "1. Ask a Question",
        "2. Describe Image"
    ]
    send_message(recipient_id, "Choose an option:\n" + "\n".join(options))

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

def get_huggingface_question_response(question):
    messages = [{"role": "user", "content": question}]
    
    try:
        response = client.chat_completion(
            model="meta-llama/Meta-Llama-3-8B-Instruct",
            messages=messages,
            max_tokens=500,
            stream=True,
        )

        text = "".join(message.choices[0].delta.content for message in response)

        if not text:
            return "I'm sorry, I couldn't generate a response. Can you please ask something else?"

        return text
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
            stream=True,
        )

        text = "".join(message.choices[0].delta.content for message in response)

        if not text:
            return "I'm sorry, I couldn't generate a response. Can you please ask something else?"

        return text
    except Exception as e:
        print(f"Error getting response from Hugging Face: {e}")
        return "Sorry, I'm having trouble responding right now."

if __name__ == '__main__':
    app.run(port=5000, debug=True)
