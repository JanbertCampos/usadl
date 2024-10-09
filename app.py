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
                attachments = event['message'].get('attachments', [])

                if sender_id not in user_context:
                    user_context[sender_id] = {'last_question': None, 'last_answer': None, 'context': [], 'image_description': None}

                if user_message.lower() == "ask for a question":
                    send_response(sender_id, "Please type your question.")
                elif user_message.lower() == "describe an image":
                    send_response(sender_id, "Please Send an image")
                elif attachments:
                    process_image_attachment(sender_id, attachments)
                else:
                    process_user_request(sender_id, user_message)
    except Exception as e:
        print(f"Error processing message: {e}")

def process_image_attachment(sender_id, attachments):
    image_url = attachments[0]['payload']['url']
    model = "meta-llama/Llama-3.2-11B-Vision-Instruct"
    
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
    
    description = response['choices'][0]['message']['content']
    send_response(sender_id, description)
    
    user_context[sender_id]['last_answer'] = description
    user_context[sender_id]['image_description'] = description

def process_user_request(sender_id, content):
    context = user_context[sender_id]
    context['last_question'] = content

    if context['image_description']:
        context['context'].append({"question": context['last_question'], "answer": context['image_description']})

    model = "meta-llama/Llama-3.2-3B-Instruct"
    response = client.chat_completion(
        model=model,
        messages=[{"role": "user", "content": content}] + 
                  [{"role": "system", "content": f"Previous interactions: {ctx['question']} -> {ctx['answer']}"}
                   for ctx in context['context']],
        max_tokens=500,
    )

    answer = response['choices'][0]['message']['content']
    context['last_answer'] = answer
    send_response(sender_id, answer)

    # Handle specific follow-up questions
    if "color scheme" in content.lower():
        send_response(sender_id, "To help me identify the color schemes, could you describe any colors or styles you remember from the image?")
    
    user_context[sender_id] = context

def send_response(sender_id, message):
    if not sender_id:
        print("Invalid sender ID. Cannot send response.")
        return

    if len(message) > 2000:
        message = message[:2000]

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
