from flask import Flask, request
import requests
import os
from huggingface_hub import InferenceClient

app = Flask(__name__)

# Replace with your actual tokens
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
HUGGINGFACES_API_KEY = os.environ.get('HUGGINGFACES_API_KEY')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '12345')

# Dictionary to store user conversations and contexts
user_contexts = {}

# Initialize the Hugging Face API client
client = InferenceClient(api_key=HUGGINGFACES_API_KEY)

@app.route('/webhook', methods=['GET'])
def verify():
    """Verify the webhook for Facebook Messenger."""
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
            message_text = event.get('message', {}).get('text')
            image_url = None

            if 'attachments' in event['message']:
                for attachment in event['message']['attachments']:
                    if attachment['type'] == 'image':
                        image_url = attachment['payload']['url']
                        print(f"Image detected: {image_url}")

            # Handle text messages or image attachments
            response_text = get_response_based_on_message(sender_id, message_text, image_url)
            send_message(sender_id, response_text)

    return 'OK', 200

def get_response_based_on_message(sender_id, message_text, image_url):
    """Get a response based on the message or image."""
    # Initialize user context if it doesn't exist
    if sender_id not in user_contexts:
        user_contexts[sender_id] = {'image_description': None}

    if image_url:
        # Analyze the image and store the description
        description = analyze_image(image_url)
        user_contexts[sender_id]['image_description'] = description
        return description
    elif message_text:
        # Respond to follow-up questions based on the stored image description
        image_description = user_contexts[sender_id].get('image_description')
        if image_description:
            return handle_follow_up_question(message_text, image_description)
        return "I didn't understand that."

    return "I received your message but need to process it further."

def handle_follow_up_question(question, image_description):
    """Handle follow-up questions about the image."""
    if "color" in question.lower():
        # You can parse the description for colors or give a default answer
        return "The main color I see is navy blue."
    elif "what mostly code" in question.lower():
        # You can customize responses based on known descriptions
        return "The code is primarily JavaScript, PHP, and HTML."
    # Add more conditions for different types of follow-up questions
    return "I'm not sure how to answer that. Can you ask something else?"

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
            stream=False,
        )

        if hasattr(response, 'choices') and len(response.choices) > 0:
            description = response.choices[0].message['content'].strip()
            print(f"Image description: {description}")
            return description

        return "I'm sorry, I couldn't generate a description for that image."

    except Exception as e:
        print(f"Error analyzing image: {e}")
        return "Sorry, I'm having trouble analyzing that image right now."

def send_message(recipient_id, message_text):
    """Send a message back to the user."""
    payload = {
        'messaging_type': 'RESPONSE',
        'recipient': {'id': recipient_id},
        'message': {'text': message_text}
    }
    response = requests.post(f'https://graph.facebook.com/v12.0/me/messages?access_token={PAGE_ACCESS_TOKEN}', json=payload)

    if response.status_code != 200:
        print(f"Failed to send message: {response.text}")
    else:
        print(f"Message sent successfully to {recipient_id}: {message_text}")

if __name__ == '__main__':
    app.run(port=5000, debug=True)
