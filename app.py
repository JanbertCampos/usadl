from flask import Flask, request
import os
import requests
from huggingface_hub import InferenceClient

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
HUGGINGFACES_API_KEY = os.environ.get('HUGGINGFACES_API_KEY')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '12345')

client = InferenceClient(api_key=HUGGINGFACES_API_KEY)

# Dictionary to hold user contexts
user_context = {}

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
    try:
        messaging_events = data['entry'][0]['messaging']
        for event in messaging_events:
            sender_id = event['sender']['id']
            if 'message' in event:
                user_message = event['message'].get('text', '')
                
                # Initialize user context if not present
                if sender_id not in user_context:
                    user_context[sender_id] = {'last_question': None, 'last_answer': None}

                if user_message.lower() == "ask for a question":
                    send_response(sender_id, "Please type your question.")
                elif user_message.lower() == "describe an image":
                    send_response(sender_id, "Please provide the image URL.")
                else:
                    process_user_request(sender_id, user_message)
    except Exception as e:
        print(f"Error processing message: {e}")

def process_user_request(sender_id, content):
    context = user_context[sender_id]
    
    # Save the content as the last question
    context['last_question'] = content

    if "http" in content:  # Check for image URL
        model = "meta-llama/Llama-3.2-11B-Vision-Instruct"
        response = client.chat_completion(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": content}},
                    {"type": "text", "text": "Describe this image in one sentence."},
                ],
            }],
            max_tokens=500,
        )
        description = response['choices'][0]['message']['content']
        context['last_answer'] = description  # Save the answer to the context
        send_response(sender_id, description)
    else:
        model = "meta-llama/Llama-3.2-3B-Instruct"
        response = client.chat_completion(
            model=model,
            messages=[{"role": "user", "content": content}],
            max_tokens=500,
        )
        answer = response['choices'][0]['message']['content']
        context['last_answer'] = answer  # Save the answer to the context
        send_response(sender_id, answer)

    # Update user context
    user_context[sender_id] = context

def send_response(sender_id, message):
    if not sender_id:
        print("Invalid sender ID. Cannot send response.")
        return

    # Ensure the message is within the allowed length
    if len(message) > 2000:
        message = message[:2000]  # Truncate to 2000 characters

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
