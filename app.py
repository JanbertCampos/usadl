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

@app.route('/enable_inputs', methods=['POST'])
def enable_inputs():
    result = client.predict(api_name="/enable_inputs")
    return jsonify(result)

@app.route('/reset_textbox', methods=['POST'])
def reset_textbox():
    result = client.predict(api_name="/reset_textbox")
    return jsonify(result)

@app.route('/predict', methods=['POST'])
def predict():
    data = request.json
    inputs = data.get('inputs', "Hello!!")
    top_p = data.get('top_p', 1.0)
    temperature = data.get('temperature', 1.0)
    chat_counter = data.get('chat_counter', 0)
    chatbot = data.get('chatbot', [])
    
    result = client.predict(
        inputs=inputs,
        top_p=top_p,
        temperature=temperature,
        chat_counter=chat_counter,
        chatbot=chatbot,
        api_name="/predict"
    )
    return jsonify(result)

@app.route('/reset_textbox_1', methods=['POST'])
def reset_textbox_1():
    result = client.predict(api_name="/reset_textbox_1")
    return jsonify(result)

@app.route('/predict_1', methods=['POST'])
def predict_1():
    data = request.json
    inputs = data.get('inputs', "Hello!!")
    top_p = data.get('top_p', 1.0)
    temperature = data.get('temperature', 1.0)
    chat_counter = data.get('chat_counter', 0)
    chatbot = data.get('chatbot', [])
    
    result = client.predict(
        inputs=inputs,
        top_p=top_p,
        temperature=temperature,
        chat_counter=chat_counter,
        chatbot=chatbot,
        api_name="/predict_1"
    )
    return jsonify(result)

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
    # Call the AI model to get a response
    # Specify the api_name that you want to use (e.g., "/predict")
    result = client.predict(inputs=message_text, api_name="/predict")
    return result[0][0]  # Assuming the response is in the first element of the result tuple


def send_message(recipient_id, message_text):
    """Send a message to a user on Facebook Messenger."""
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
