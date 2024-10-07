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
        token = request.args.get('hub.verify_token')
        if token == VERIFY_TOKEN:
            return request.args.get('hub.challenge')
        return "Verification token mismatch", 403

    data = request.json
    if 'object' in data and data['object'] == 'page':
        for entry in data['entry']:
            for messaging_event in entry['messaging']:
                sender_id = messaging_event['sender']['id']
                message_text = messaging_event['message']['text']
                
                # Process the user's message
                response_text = handle_user_message(message_text)
                send_message(sender_id, response_text)
    
    return jsonify(status="success"), 200

def handle_user_message(message_text):
    global chat_history
    
    # Optional: Reset chat history based on specific keywords
    if message_text.lower() in ["reset", "start over"]:
        chat_history = []
        return "Chat history has been reset. How can I assist you today?"
    
    chat_history.append(message_text)  # Append the user's message to chat history
    print(f"Chat history: {chat_history}")  # Debug log

    # Generate the input for the model based on chat history
    model_input = "\n".join(chat_history)  # Join messages with new lines for context
    result = client.predict(inputs=model_input, top_p=0.9, temperature=0.7, api_name="/predict")
    
    # Assuming the model returns a response as the last part of the conversation
    response_text = result[0][0] if result else "I didn't understand that."
    chat_history.append(response_text)  # Append the model's response to chat history
    print(f"Response from model: {response_text}")  # Debug log
    return response_text

def send_message(recipient_id, message_text):
    if not message_text:
        message_text = "I didn't understand that."
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
