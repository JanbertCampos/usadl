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
AI_INSTRUCTIONS = (
    "You are JanbertGwapo, a helpful and super intelligent being in the entire universe. Please be polite and kind."
)

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
            message_attachments = event.get('message', {}).get('attachments', [])

            # Retrieve or initialize the conversation context
            context = user_contexts.get(sender_id, {'messages': []})

            if message_text:
                print(f"Received message from {sender_id}: {message_text}")
                context['messages'].append(message_text)

            # Check for attachments (like images)
            for attachment in message_attachments:
                if attachment['type'] == 'image':
                    image_url = attachment['payload']['url']
                    context['messages'].append(image_url)

            # Send typing indicator
            send_typing_indicator(sender_id)

            # Get response from Hugging Face model
            response_text = get_huggingface_response(context)
            print(f"Full response: {response_text}")

            # Send the response back to the user
            send_message(sender_id, response_text)

            # Store updated context
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
    time.sleep(1)  # Simulate typing delay (optional)

def get_huggingface_response(context):
    messages = []
    user_messages = context['messages'][-10:]  # Get the last 10 messages

    for msg in user_messages:
        if "http" in msg:  # Check for image URLs
            messages.append({
                "type": "image_url",
                "image_url": {"url": msg}
            })
        else:
            messages.append({
                "type": "text",
                "text": msg
            })

    try:
        response = client.chat_completion(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            messages=[{"role": "user", "content": messages}],
            max_tokens=500,
            stream=False,
        )

        text = response.choices[0].message['content'] if response.choices else ""

        # Check for empty responses
        if not text:
            return "I'm sorry, I didn't quite understand that. Could you rephrase?"

        # Limit repetitive fallback responses
        recent_responses = context.get('recent_responses', [])
        fallback_count = context.get('fallback_count', 0)

        if text in recent_responses[-3:]:
            fallback_count += 1
            if fallback_count >= 3:  # Limit to 3 consecutive fallbacks
                return "I'm really not sure how to assist you. Maybe you could try asking something else?"
            context['fallback_count'] = fallback_count
            return "I'm still not sure how to help with that. Could you provide more details?"

        # Reset fallback count if a valid response is received
        context['fallback_count'] = 0

        # Store the current response in recent responses
        recent_responses.append(text)
        context['recent_responses'] = recent_responses[-5:]  # Keep last 5 responses

        return text
    except Exception as e:
        print(f"Error getting response from Hugging Face: {e}")
        return "Sorry, I'm having trouble responding right now."

if __name__ == '__main__':
    app.run(port=5000, debug=True)