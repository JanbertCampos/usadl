from flask import Flask, request
import requests
import json
import os
from huggingface_hub import InferenceClient

app = Flask(__name__)

# Replace with your actual tokens
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
HUGGINGFACE_API_KEY = os.environ.get('HUGGINGFACE_API_KEY')  # Use the Hugging Face API key
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '12345')

# Initialize the Hugging Face client
client = InferenceClient(api_key=HUGGINGFACE_API_KEY)

# Instructions for the AI
AI_INSTRUCTIONS = (
    "You are Janbert, a helpful assistant. "
    "Your primary goal is to provide insightful and informative responses while maintaining a friendly demeanor. "
    "Feel free to share jokes and light-hearted comments, making the conversation enjoyable. "
    "When users ask for song lyrics, provide them directly instead of summarizing or redirecting. "
    "You are equipped to handle inquiries about current events or real-time information, such as weather updates and sports scores. "
    "If the user asks about a term you are unfamiliar with, be open to exploring it, as it might be something new. "
    "Additionally, if a user explicitly requests you to browse or provide links to references, you should summarize the information in a conversational manner. "
    "You can communicate in multiple languages, so impress users with your skills! "
    "Always remember that a good laugh is just as important as a good answer!"
)

# Dictionary to store user conversations and topics
user_contexts = {}

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
            message_text = event.get('message', {}).get('text')
            customer_name = event.get('message', {}).get('customer', {}).get('first_name', 'there')

            if message_text:
                print(f"Received message from {sender_id}: {message_text}")

                # Retrieve or initialize the conversation context
                context = user_contexts.get(sender_id, {'messages': [], 'previous_topics': []})
                context['messages'].append(message_text)  # Add the new message to the context

                # Detect if the user is changing the topic
                if context['messages']:
                    # Only check for the second-to-last message if it exists
                    if len(context['messages']) > 1 and context['messages'][-2] != message_text:
                        context['previous_topics'].append(context['messages'][-2])  # Store the previous topic

                # Get response from Hugging Face model
                response_text = get_huggingface_response(context)
                
                # Mention the customer's name in the response
                response_text = f"Hi {customer_name}, {response_text}"
                print(f"Full response: {response_text}")

                # Send the response back to the user
                send_message(sender_id, response_text)

                # Store updated context
                user_contexts[sender_id] = context

    return 'OK', 200

def send_message(recipient_id, message_text):
    max_length = 2000
    part_num = 1
    while message_text:
        part = message_text[:max_length]
        message_text = message_text[max_length:]

        if message_text:
            part_info = f"Part {part_num} of {len(message_text) // max_length + 1}"
            part = f"{part_info}: {part}"
        
        payload = {
            'messaging_type': 'RESPONSE',
            'recipient': {'id': recipient_id},
            'message': {'text': part}
        }
        print(f"Sending message to {recipient_id}: {part}")
        response = requests.post(f'https://graph.facebook.com/v12.0/me/messages?access_token={PAGE_ACCESS_TOKEN}', json=payload)
        if response.status_code != 200:
            print(f"Failed to send message: {response.text}")
        else:
            print(f"Message sent successfully to {recipient_id}: {part}")
        part_num += 1

def get_huggingface_response(context):
    user_input = " ".join(context['messages'])
    user_input = f"{AI_INSTRUCTIONS} {user_input}"

    try:
        # Call the Hugging Face API
        response = client.chat_completion(
            model="meta-llama/Meta-Llama-3-8B-Instruct",
            messages=[{"role": "user", "content": user_input}],
            max_tokens=500,
            stream=False,  # Set to False to wait for the full response
        )

        # Extract the content from the response
        response_text = response[0]['choices'][0]['message']['content']
        return response_text if response_text else "I'm sorry, I couldn't generate a response."
    
    except Exception as e:
        print(f"Error getting response from Hugging Face: {e}")
        return "Sorry, I'm having trouble responding right now."

if __name__ == '__main__':
    app.run(port=5000, debug=True)
