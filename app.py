import os
import requests
from flask import Flask, request, jsonify
from gradio_client import Client

# Load environment variables
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
HUGGINGFACES_API_KEY = os.environ.get('HUGGINGFACES_API_KEY')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '12345')

app = Flask(__name__)
client = Client("yuntian-deng/ChatGPT4")

# Store recent messages and responses for context
user_messages = {}
model_responses = {}

@app.route('/', methods=['GET'])
def index():
    return "Webhook is running", 200

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        token = request.args.get('hub.verify_token')
        if token == VERIFY_TOKEN:
            return request.args.get('hub.challenge')
        return "Verification token mismatch", 403

    data = request.json
    if 'object' in data and data['object'] == 'page':
        for entry in data['entry']:
            for messaging_event in entry['messaging']:
                sender_id = messaging_event['sender']['id']
                
                if 'message' in messaging_event and 'text' in messaging_event['message']:
                    message_text = messaging_event['message']['text']
                    print(f"Received message from {sender_id}: {message_text}")

                    response_text = handle_user_message(sender_id, message_text)
                    send_message(sender_id, response_text)
                else:
                    print(f"Received unsupported message type from user {sender_id}")

    return jsonify(status="success"), 200

def handle_user_message(sender_id, message_text):
    global user_messages, model_responses

    if sender_id not in user_messages:
        user_messages[sender_id] = []
        model_responses[sender_id] = []

    user_messages[sender_id].append(message_text)

    # Use the last 5 messages to create the model input
    model_input = "\n".join(user_messages[sender_id][-5:])  
    print(f"Chat history: {model_input}")

    try:
        # Call the predict API with appropriate parameters
        result = client.predict(
            inputs=model_input,
            top_p=0.9,
            temperature=0.7,
            chat_counter=len(user_messages[sender_id]),
            chatbot=user_messages[sender_id][-5:],  # Use last 5 messages
            api_name="/predict"
        )
        
        # Extract the first element of the result, which contains the model response
        response_text = result[0][0] if isinstance(result, tuple) else "I didn't understand that."
    except Exception as e:
        print(f"Error calling the AI model: {e}")
        response_text = "I'm having trouble responding right now."

    response_text = response_text.replace("'", "").replace("[", "").replace("]", "").strip()

    # Add a fallback mechanism for repeated misunderstandings
    if model_responses[sender_id] and response_text == model_responses[sender_id][-1]:
        response_text = "I'm sorry, can you ask me something else?"

    model_responses[sender_id].append(response_text)

    print(f"Response from model: {response_text}")
    return response_text

def send_message(recipient_id, message_text):
    if not message_text:
        message_text = "I didn't understand that."

    message_text = str(message_text).encode('utf-8', 'ignore').decode('utf-8')

    url = f'https://graph.facebook.com/v11.0/me/messages?access_token={PAGE_ACCESS_TOKEN}'
    headers = {'Content-Type': 'application/json'}
    payload = {'recipient': {'id': recipient_id}, 'message': {'text': message_text}}

    print(f"Sending message to {recipient_id}: {message_text}")

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        print(f"Error sending message: {response.status_code} - {response.text}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
