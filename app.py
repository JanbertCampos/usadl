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
passcode = "babyko"

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
                attachments = event['message'].get('attachments', [])

                # Initialize user context if not present
                if sender_id not in user_context:
                    user_context[sender_id] = {
                        'last_question': None,
                        'last_answer': None,
                        'context': [],
                        'image_description': None,
                        'authenticated': False
                    }
                    send_response(sender_id, "Welcome! Please enter the passcode.")

                context = user_context[sender_id]

                # Passcode check
                if not context['authenticated']:
                    if user_message.lower() == passcode:
                        context['authenticated'] = True
                        send_response(sender_id, "Access granted! You can now use the commands: 'ask for a question' and 'describe an image'.")
                    else:
                        send_response(sender_id, "bobo incorrect passcode please try again")
                else:
                    # Handle commands after authentication
                    if user_message.lower() == "ask for a question":
                        send_response(sender_id, "Please type your question.")
                    elif user_message.lower() == "describe an image":
                        send_response(sender_id, "Please send an image.")
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

    if response and 'choices' in response:
        description = response['choices'][0]['message']['content']
        send_response(sender_id, description)
        
        # Store description and keywords
        user_context[sender_id]['last_answer'] = description
        user_context[sender_id]['image_description'] = description
        user_context[sender_id]['image_data'] = {'url': image_url, 'description': description}
        user_context[sender_id]['image_keywords'] = ['phpMyAdmin', 'error']  # Add relevant keywords



def process_user_request(sender_id, content):
    context = user_context[sender_id]
    context['last_question'] = content

    # Check if the user is asking for solutions related to the last image
    if context['image_data'] and ("solution" in content.lower() or "fix" in content.lower() or "error" in content.lower()):
        description = context['image_data']['description']
        if "1045" in description:  # Example keyword from the image description
            send_response(sender_id, "The error 1045 indicates incorrect MySQL credentials. Possible solutions include: 1. Checking your MySQL username and password. 2. Ensuring that the user has the proper privileges. 3. Reviewing your MySQL configuration settings.")
            return
        else:
            send_response(sender_id, "I'm not sure how to address that specific issue. Could you provide more context or details?")

    # Log the current question
    context['context'].append({"question": content, "answer": None})

    # Prepare previous interactions
    previous_interactions = [
        {"role": "system", "content": f"Previous interactions: {ctx['question']} -> {ctx['answer']}"}
        for ctx in context['context'] if 'question' in ctx and 'answer' in ctx
    ]

    response = client.chat_completion(
        model="meta-llama/Llama-3.2-3B-Instruct",
        messages=[{"role": "user", "content": content}] + previous_interactions,
        max_tokens=500,
    )

    if response and 'choices' in response:
        answer = response['choices'][0]['message']['content']
        if answer.strip():
            context['last_answer'] = answer
            context['context'][-1]['answer'] = answer
            send_response(sender_id, answer)
        else:
            send_response(sender_id, "I couldn't find an answer to that. Can you ask something else?")
    else:
        send_response(sender_id, "There was an error processing your request. Can you please rephrase your question?")

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


