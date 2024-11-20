from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flasgger import Swagger, swag_from
import os
import requests
import json
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import logging

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure Swagger
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,  # Include all endpoints
            "model_filter": lambda tag: True,  # Include all tags
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/swagger/",
}
swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Article Generator API",
        "description": "API for generating articles using Sambanova AI.",
        "version": "1.0.0",
    },
    "host": "localhost:5000",  # Change to your server host
    "basePath": "/",
    "schemes": ["http"],
}
swagger = Swagger(app, config=swagger_config, template=swagger_template)

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for more detailed logs
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Retrieve the Sambanova API key from environment variables
SAMBANOVA_API_KEY = os.getenv("SAMBANOVA_API_KEY")

# Sambanova AI API endpoints
SAMBANOVA_CHAT_API_URL = "https://api.sambanova.ai/v1/chat/completions"

# Maximum allowed tokens for the model
MAX_TOKENS = 16384
RESERVED_TOKENS = 1000
MAX_SYLLABUS_TOKENS = MAX_TOKENS - RESERVED_TOKENS  # 15384 tokens

@app.route('/')
def home():
    """Home route.
    ---
    responses:
      200:
        description: Welcome message
    """
    return "Welcome to the Article Generator API!"

@app.route('/generate-article', methods=['POST'])
@swag_from({
    "tags": ["Article Generation"],
    "description": "Generate an article based on a given topic using Sambanova AI.",
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "example": "Artificial Intelligence in Healthcare",
                    }
                },
                "required": ["topic"]
            }
        }
    ],
    "responses": {
        200: {
            "description": "Article generated successfully",
            "schema": {
                "type": "object",
                "properties": {
                    "article": {
                        "type": "string",
                        "example": "Artificial intelligence (AI) is transforming the healthcare industry by enabling faster diagnosis...",
                    }
                }
            }
        },
        400: {"description": "Invalid input"},
        502: {"description": "Error communicating with Sambanova AI API"},
        500: {"description": "Internal server error"}
    }
})
def generate_article():
    try:
        data = request.get_json()

        # Validate the input
        if not data or 'topic' not in data:
            logger.warning("No topic provided in the request.")
            return jsonify({'error': 'No topic provided'}), 400

        topic = data['topic'].strip()

        if not topic:
            logger.warning("Empty topic provided in the request.")
            return jsonify({'error': 'Empty topic provided'}), 400

        # Prepare the payload for Sambanova AI API with enhanced prompt tuning
        payload = {
            "stream": False,  # Set to True if you want streaming responses
            "model": "Meta-Llama-3.1-8B-Instruct",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a highly knowledgeable assistant specialized in engineering and technical subjects. "
                        "You will only respond to technical questions and topics. "
                        "Your responses should be lucid, easy to understand, and rich with real-life examples to illustrate your points."
                    )
                },
                {
                    "role": "user",
                    "content": f"Generate an article about {topic}."
                }
            ]
        }

        # Set up headers with authorization
        headers = {
            "Authorization": f"Bearer {SAMBANOVA_API_KEY}",
            "Content-Type": "application/json"
        }

        logger.info(f"Sending request to Sambanova AI API for topic: {topic}")

        # Make the POST request to Sambanova AI API
        response = requests.post(
            SAMBANOVA_CHAT_API_URL,
            json=payload,
            headers=headers,
            stream=payload.get("stream", False)
        )

        # Check if the request was successful
        if response.status_code != 200:
            logger.error(f"Sambanova API error: {response.status_code} - {response.text}")
            return jsonify({'error': f"Sambanova API error: {response.text}"}), response.status_code

        if payload.get("stream", False):
            # Handle streaming response
            def generate():
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("data: "):
                            json_str = decoded_line[6:]
                            if json_str == "[DONE]":
                                break
                            try:
                                data = json.loads(json_str)
                                yield f"data: {data['choices'][0]['message']['content']}\n\n"
                            except json.JSONDecodeError:
                                continue
            logger.info("Streaming response from Sambanova AI API.")
            return Response(generate(), mimetype='text/event-stream')
        else:
            # Handle non-streaming response
            json_response = response.json()
            # Safely extract the article content
            try:
                article = json_response['choices'][0]['message']['content'].strip()
                logger.info(f"Article generated successfully for topic: {topic}")
            except (KeyError, IndexError) as e:
                logger.error("Unexpected response structure from Sambanova API.")
                logger.debug(f"Sambanova API Response: {json_response}")
                return jsonify({'error': 'Unexpected response structure from Sambanova API.'}), 502
            return jsonify({'article': article}), 200

    except requests.exceptions.RequestException as e:
        # Handle request exceptions (e.g., network issues)
        logger.error(f"Request exception: {str(e)}")
        return jsonify({'error': f"Request exception: {str(e)}"}), 502
    except Exception as e:
        # Handle general exceptions
        logger.error(f"Server error: {str(e)}")
        return jsonify({'error': f"Server error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
