from flask import Flask, request
import requests
import os
from gradio_client import Client
import time

app = Flask(__name__)

# Replace with your actual tokens
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '12345')

# Initialize the Gradio API client
client = Client("yuntian-deng/ChatGPT")

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

            if message_text:
                print(f"Received message from {sender_id}: {message_text}")

                # Retrieve or initialize the conversation context
                context = user_contexts.get(sender_id, {'messages': []})
                context['messages'].append(message_text)

                # Send typing indicator
                send_typing_indicator(sender_id)

                # Get response from ChatGPT API
                response_text = get_chatgpt_response(message_text)
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

def get_chatgpt_response(user_input):
    try:
        # Call the predict method with the correct parameters
        result = client.predict(
            inputs=user_input,  # Pass the user input as the first argument
            top_p=1,
            temperature=1,
            chat_counter=0,
            chatbot=[],  # Adjust if necessary
            api_name="/predict"  # Ensure this matches the endpoint you're using
        )
        return result[0]  # Assuming the first element is the response text
    except Exception as e:
        print(f"Error getting response from ChatGPT: {e}")
        return "Sorry, I'm having trouble responding right now."

if __name__ == '__main__':
    app.run(port=5000, debug=True)
