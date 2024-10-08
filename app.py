from flask import Flask, request
import os
import requests
from huggingface_hub import InferenceClient

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
HUGGINGFACES_API_KEY = os.environ.get('HUGGINGFACES_API_KEY')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '12345')

client = InferenceClient(api_key=HUGGINGFACES_API_KEY)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Verification for the webhook
        token = request.args.get('hub.verify_token')
        if token == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        return "Verification token mismatch", 403

    if request.method == 'POST':
        data = request.json
        handle_message(data)
        return "Message processed", 200

def handle_message(data):
    user_selection = data.get('selection')  # e.g., 'ask for a question' or 'describe an image'
    content = data.get('content')  # e.g., question text or image URL

    if user_selection == "ask for a question":
        model = "meta-llama/Llama-3.2-3B-Instruct"
        response = client.chat_completion(
            model=model,
            messages=[{"role": "user", "content": content}],
            max_tokens=500,
        )
        answer = response.choices[0].delta.content
        send_response(data['sender_id'], answer)

    elif user_selection == "describe an image":
        model = "meta-llama/Llama-3.2-11B-Vision-Instruct"
        image_url = content
        
        response = client.chat_completion(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": "Describe this image in one sentence."},
                ],
            }],
            max_tokens=500,
        )
        description = response.choices[0].delta.content
        send_response(data['sender_id'], description)

def send_response(sender_id, message):
    url = f"https://graph.facebook.com/v11.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": sender_id},
        "message": {"text": message}
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        print(f"Error sending message: {response.status_code} - {response.text}")

if __name__ == '__main__':
    app.run(port=5000)
