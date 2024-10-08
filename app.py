from flask import Flask, request
import requests
import os
from huggingface_hub import InferenceClient

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
HUGGINGFACES_API_KEY = os.environ.get('HUGGINGFACES_API_KEY')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '12345')

client = InferenceClient(api_key=HUGGINGFACES_API_KEY)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Verify the webhook
        if request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge')
        return 'Verification token mismatch', 403

    elif request.method == 'POST':
        data = request.json
        # Extract message and sender
        message_text = data['entry'][0]['messaging'][0]['message']['text']
        sender_id = data['entry'][0]['messaging'][0]['sender']['id']

        # Determine action based on message
        if "describe" in message_text:
            image_url = extract_image_url(message_text)  # Implement this function
            model = "meta-llama/Llama-3.2-11B-Vision-Instruct"
            messages = [
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": "Describe this image."}
                ]}
            ]
        else:
            model = "meta-llama/Llama-3.2-3B-Instruct"
            messages = [{"role": "user", "content": message_text}]

        # Call the Hugging Face API
        response = client.chat_completion(
            model=model,
            messages=messages,
            max_tokens=500
        )

        # Send response back to user
        reply_text = response.choices[0].delta.content
        send_message(sender_id, reply_text)  # Function to send messages back

        return 'Message processed', 200

def send_message(recipient_id, text):
    url = f'https://graph.facebook.com/v2.6/me/messages?access_token={PAGE_ACCESS_TOKEN}'
    payload = {
        'recipient': {'id': recipient_id},
        'message': {'text': text}
    }
    requests.post(url, json=payload)

def extract_image_url(message_text):
    # Logic to extract image URL from the message text
    # This is a placeholder; you should implement your own extraction logic
    # For example, you might look for a URL in the text
    return "extracted_image_url"

if __name__ == '__main__':
    app.run(port=5000)