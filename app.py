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
            message = event.get('message')

            if message and 'attachments' in message:
                for attachment in message['attachments']:
                    if attachment['type'] == 'image':
                        image_url = attachment['payload']['url']
                        print(f"Received image from {sender_id}: {image_url}")

                        # Analyze the image and get a description
                        description = analyze_image(image_url)

                        # Send the response back to the user
                        send_message(sender_id, description)

    return 'OK', 200

def analyze_image(image_url):
    try:
        response = client.chat_completion(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": "Describe this image in one sentence."},
                    ],
                }
            ],
            max_tokens=500,
            stream=False,  # Set to False to get the complete response at once
        )

        # Check if response has choices and extract the content
        if hasattr(response, 'choices') and len(response.choices) > 0:
            return response.choices[0].message['content'].strip()  # Use 'message' instead of 'delta'

        return "I'm sorry, I couldn't generate a description for that image."

    except Exception as e:
        print(f"Error analyzing image: {e}")
        return "Sorry, I'm having trouble analyzing that image right now."



def send_message(recipient_id, message_text):
    payload = {
        'messaging_type': 'RESPONSE',
        'recipient': {'id': recipient_id},
        'message': {'text': message_text}
    }
    response = requests.post(
        f'https://graph.facebook.com/v12.0/me/messages?access_token={PAGE_ACCESS_TOKEN}',
        json=payload
    )
    if response.status_code != 200:
        print(f"Failed to send message: {response.text}")
    else:
        print(f"Message sent successfully to {recipient_id}: {message_text}")

if __name__ == '__main__':
    app.run(port=5000, debug=True)
