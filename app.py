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

chat_history = []  # To store conversation history

@app.route('/', methods=['GET'])
def index():
    return "Webhook is running", 200

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Verification token for Facebook Webhook
        token = request.args.get('hub.verify_token')
        if token == VERIFY_TOKEN:
            return request.args.get('hub.challenge')
        return "Verification token mismatch", 403

    # Handle POST requests from the webhook
    data = request.json
    if 'object' in data and data['object'] == 'page':
        for entry in data['entry']:
            for messaging_event in entry['messaging']:
                sender_id = messaging_event['sender']['id']  # ID of the user who sent the message
                message_text = messaging_event['message']['text']  # Text sent by the user
                
                # Process the user's message with your AI model
                response_text = handle_user_message(message_text)
                
                # Send the response back to the user
                send_message(sender_id, response_text)
    
    return jsonify(status="success"), 200

def handle_user_message(message_text):
    global chat_history
    chat_history.append(message_text)  # Append the user's message to chat history
    
    # Construct the model input from chat history
    model_input = "\n".join(chat_history[-5:])  # Limit to the last 5 messages for context
    print(f"Chat history: {model_input}")  # Debug log
    
    # Get a response from the model
    result = client.predict(inputs=model_input, top_p=0.9, temperature=0.7, api_name="/predict")
    response_text = result[0][0] if result else "I didn't understand that."
    
    # Check for repeated responses
    if chat_history and response_text == chat_history[-1]:
        response_text = "I'm sorry, can you ask me something else?"
    
    chat_history.append(response_text)  # Append the model's response to chat history
    print(f"Response from model: {response_text}")  # Debug log
    return response_text

def send_message(recipient_id, message_text):
    """Send a message to a user on Facebook Messenger."""
    if not message_text:
        message_text = "I didn't understand that."  # Default response if empty

    # Ensure the message is a UTF-8 encoded string
    message_text = str(message_text).encode('utf-8', 'ignore').decode('utf-8')

    url = f'https://graph.facebook.com/v11.0/me/messages?access_token={PAGE_ACCESS_TOKEN}'
    headers = {
        'Content-Type': 'application/json'
    }
    payload = {
        'recipient': {'id': recipient_id},
        'message': {'text': message_text}
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        print(f"Error sending message: {response.status_code} - {response.text}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)