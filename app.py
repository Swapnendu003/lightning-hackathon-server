from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flasgger import Swagger, swag_from
import os
import requests
import json
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import logging
import base64
from werkzeug.datastructures import FileStorage
import re
import openai  

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
        "title": "Article and Question Generator API",
        "description": "API for generating articles and questions using Sambanova AI.",
        "version": "1.0.0",
    },
    "host": "lightning-hackathon-server.onrender.com",  # Change to your server host
    "basePath": "/",
    "schemes": ["https"],
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

# Configure upload settings
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    """Home route.
    ---
    responses:
      200:
        description: Welcome message
    """
    return "Welcome to the Article and Question Generator API!"

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
    """Endpoint to generate an article based on a given topic."""
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

@app.route('/generate-questions', methods=['POST'])
@swag_from({
    "tags": ["Question Generation"],
    "description": "Generate up to 10 questions (5 short and 5 descriptive) based on a provided syllabus. The syllabus can be provided either as text or as an uploaded image. **Provide either `syllabus_text` or `syllabus_image` in a single request, not both.**",
    "consumes": [
        "multipart/form-data",
        "application/json"
    ],
    "parameters": [
        {
            "name": "syllabus_text",
            "in": "formData",
            "type": "string",
            "required": False,
            "description": "Text of the syllabus."
        },
        {
            "name": "syllabus_image",
            "in": "formData",
            "type": "file",
            "required": False,
            "description": "Image file of the syllabus."
        }
    ],
    "responses": {
        200: {
            "description": "Questions generated successfully",
            "schema": {
                "type": "object",
                "properties": {
                    "short_questions": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "example": "What is the role of AI in healthcare?"
                        }
                    },
                    "descriptive_questions": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "example": "Explain how AI technologies can improve diagnostic accuracy in healthcare."
                        }
                    }
                }
            }
        },
        400: {"description": "Invalid input"},
        502: {"description": "Error communicating with Sambanova AI API"},
        500: {"description": "Internal server error"}
    }
})
def generate_questions():
    """Endpoint to generate questions based on a syllabus provided as text or image."""
    try:
        syllabus_text = None
        syllabus_image_present = False
        syllabus_text_present = False

        # Determine the content type of the request
        content_type = request.content_type
        logger.debug(f"Request Content-Type: {content_type}")

        # Initialize variables for form-data and JSON
        if 'multipart/form-data' in content_type:
            # Handle multipart/form-data (file upload and/or form fields)
            syllabus_image = request.files.get('syllabus_image')
            syllabus_text_field = request.form.get('syllabus_text')

            if syllabus_image and syllabus_text_field:
                logger.warning("Both syllabus_image and syllabus_text provided.")
                return jsonify({'error': 'Provide either syllabus_text or syllabus_image, not both.'}), 400
            elif syllabus_image:
                syllabus_image_present = True
            elif syllabus_text_field:
                syllabus_text_present = True
                syllabus_text = syllabus_text_field.strip()
            else:
                logger.warning("No syllabus_text or syllabus_image provided in the form-data.")
                return jsonify({'error': 'No syllabus_text or syllabus_image provided.'}), 400

        elif 'application/json' in content_type:
            # Handle application/json
            data = request.get_json()
            if not data:
                logger.warning("Empty JSON payload.")
                return jsonify({'error': 'Empty JSON payload.'}), 400

            syllabus_text_field = data.get('syllabus_text')
            if 'syllabus_image' in data:
                logger.warning("syllabus_image should be uploaded as a file, not in JSON payload.")
                return jsonify({'error': 'syllabus_image should be uploaded as a file, not in JSON payload.'}), 400
            if syllabus_text_field:
                syllabus_text_present = True
                syllabus_text = syllabus_text_field.strip()

            if not syllabus_text_present:
                logger.warning("No syllabus_text provided in the JSON payload.")
                return jsonify({'error': 'No syllabus_text provided.'}), 400
        else:
            logger.warning("Unsupported Content-Type.")
            return jsonify({'error': 'Unsupported Content-Type. Use multipart/form-data or application/json.'}), 400

        # Validate that exactly one input is provided
        if syllabus_image_present and syllabus_text_present:
            logger.warning("Both syllabus_image and syllabus_text provided.")
            return jsonify({'error': 'Provide either syllabus_text or syllabus_image, not both.'}), 400
        elif not (syllabus_image_present or syllabus_text_present):
            logger.warning("Neither syllabus_image nor syllabus_text provided.")
            return jsonify({'error': 'Provide either syllabus_text or syllabus_image.'}), 400

        # If syllabus is provided as image, extract text
        if syllabus_image_present:
            file: FileStorage = request.files['syllabus_image']

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                logger.info(f"Saved uploaded syllabus image to {file_path}")

                # Read and encode the image in base64
                with open(file_path, "rb") as image_file:
                    encoded_image = base64.b64encode(image_file.read()).decode('utf-8')

                # Prepare the payload for image to text extraction
                payload_image = {
                    "stream": False,  # Set to True if streaming is desired
                    "model": "Llama-3.2-11B-Vision-Instruct",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Extract the syllabus text from the following image."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/{filename.rsplit('.',1)[1].lower()};base64,{encoded_image}"
                                    }
                                }
                            ]
                        }
                    ]
                }

                headers_image = {
                    "Authorization": f"Bearer {SAMBANOVA_API_KEY}",
                    "Content-Type": "application/json"
                }

                logger.info("Sending image to Sambanova AI API for text extraction.")

                # Make the POST request to extract text from image
                response_image = requests.post(
                    SAMBANOVA_CHAT_API_URL,
                    json=payload_image,
                    headers=headers_image,
                    stream=payload_image.get("stream", False)
                )

                # Check if the request was successful
                if response_image.status_code != 200:
                    logger.error(f"Sambanova API error during image processing: {response_image.status_code} - {response_image.text}")
                    return jsonify({'error': f"Sambanova API error during image processing: {response_image.text}"}), response_image.status_code

                json_response_image = response_image.json()
                try:
                    syllabus_text = json_response_image['choices'][0]['message']['content'].strip()
                    logger.info("Extracted syllabus text from image successfully.")
                except (KeyError, IndexError) as e:
                    logger.error("Unexpected response structure from Sambanova API during image processing.")
                    logger.debug(f"Sambanova API Response: {json_response_image}")
                    return jsonify({'error': 'Unexpected response structure from Sambanova API during image processing.'}), 502

                # Optionally, delete the uploaded image after processing
                os.remove(file_path)
                logger.info(f"Deleted uploaded image file {file_path} after processing.")
            else:
                logger.warning("Invalid or no file uploaded.")
                return jsonify({'error': 'Invalid or no file uploaded. Please upload a valid image file.'}), 400

        elif syllabus_text_present:
            if not syllabus_text:
                logger.warning("Empty syllabus_text provided in the request.")
                return jsonify({'error': 'Empty syllabus_text provided.'}), 400
            logger.info("Received syllabus text from request.")

        # At this point, syllabus_text contains the syllabus either from text or extracted from image
        # Prepare the payload to generate questions
        prompt = (
            f"You are an educational assistant tasked with generating exam questions. "
            f"Based on the following syllabus, generate up to 10 questions: "
            f"5 short (multiple-choice or short-answer) questions and 5 descriptive (essay or open-ended) questions. "
            f"Ensure that the questions directly test understanding, application, and analysis of the syllabus content. Avoid generic or irrelevant questions.\n\n"
            f"Syllabus:\n{syllabus_text}"
        )

        payload_questions = {
            "stream": False,  # Set to True if streaming is desired
            "model": "Meta-Llama-3.1-8B-Instruct",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an educational assistant specialized in creating academic questions."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        headers_questions = {
            "Authorization": f"Bearer {SAMBANOVA_API_KEY}",
            "Content-Type": "application/json"
        }

        logger.info("Sending syllabus to Sambanova AI API to generate questions.")

        # Make the POST request to generate questions
        response_questions = requests.post(
            SAMBANOVA_CHAT_API_URL,
            json=payload_questions,
            headers=headers_questions,
            stream=payload_questions.get("stream", False)
        )

        # Check if the request was successful
        if response_questions.status_code != 200:
            logger.error(f"Sambanova API error during question generation: {response_questions.status_code} - {response_questions.text}")
            return jsonify({'error': f"Sambanova API error during question generation: {response_questions.text}"}), response_questions.status_code

        json_response_questions = response_questions.json()
        try:
            questions_text = json_response_questions['choices'][0]['message']['content'].strip()
            logger.info("Questions generated successfully.")
        except (KeyError, IndexError) as e:
            logger.error("Unexpected response structure from Sambanova API during question generation.")
            logger.debug(f"Sambanova API Response: {json_response_questions}")
            return jsonify({'error': 'Unexpected response structure from Sambanova API during question generation.'}), 502

        # Parse the questions into short and descriptive
        # Assuming the AI returns them in a numbered list or similar format
        short_questions = []
        descriptive_questions = []
        for line in questions_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            # Match patterns like "1. Question", "2. Question", etc.
            if re.match(r'^[1-5]\.\s+', line):
                short_questions.append(re.sub(r'^[1-5]\.\s+', '', line))
            elif re.match(r'^[6-9]\.\s+', line) or re.match(r'^10\.\s+', line):
                descriptive_questions.append(re.sub(r'^[6-9]?\d\.\s+', '', line))

        # Limit the number of questions to 5 per category, but don't enforce strict counts
        short_questions = short_questions[:5]
        descriptive_questions = descriptive_questions[:5]

        logger.info(f"Short Questions Generated: {len(short_questions)}")
        logger.info(f"Descriptive Questions Generated: {len(descriptive_questions)}")

        return jsonify({
            'short_questions': short_questions,
            'descriptive_questions': descriptive_questions
        }), 200

    except requests.exceptions.RequestException as e:
        logger.error(f"Request exception: {str(e)}")
        return jsonify({'error': f"Request exception: {str(e)}"}), 502
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        return jsonify({'error': f"Server error: {str(e)}"}), 500


@app.route('/evaluate-answer', methods=['POST'])
@swag_from({
    "tags": ["Answer Evaluation"],
    "description": "Evaluate a student's answer to a given question. Both the question and the answer should be provided as images.",
    "consumes": ["multipart/form-data"],
    "parameters": [
        {
            "name": "question_image",
            "in": "formData",
            "type": "file",
            "required": True,
            "description": "Image file of the question."
        },
        {
            "name": "answer_image",
            "in": "formData",
            "type": "file",
            "required": True,
            "description": "Image file of the student's answer."
        }
    ],
    "responses": {
        200: {
            "description": "Answer evaluated successfully",
            "schema": {
                "type": "object",
                "properties": {
                    "evaluation": {
                        "type": "string",
                        "example": "The student's answer is correct and demonstrates a clear understanding of the topic..."
                    },
                    "score": {
                        "type": "integer",
                        "example": 8
                    }
                }
            }
        },
        400: {"description": "Invalid input"},
        502: {"description": "Error communicating with APIs"},
        500: {"description": "Internal server error"}
    }
})
def evaluate_answer():
    """Endpoint to evaluate a student's answer based on the question and answer images."""
    try:
        # Check if both images are provided
        if 'question_image' not in request.files or 'answer_image' not in request.files:
            logger.warning("Both question_image and answer_image must be provided.")
            return jsonify({'error': 'Both question_image and answer_image must be provided.'}), 400

        question_image = request.files['question_image']
        answer_image = request.files['answer_image']

        # Validate the uploaded files
        if not (question_image and allowed_file(question_image.filename)):
            logger.warning("Invalid or no question_image uploaded.")
            return jsonify({'error': 'Invalid or no question_image uploaded. Please upload a valid image file.'}), 400
        if not (answer_image and allowed_file(answer_image.filename)):
            logger.warning("Invalid or no answer_image uploaded.")
            return jsonify({'error': 'Invalid or no answer_image uploaded. Please upload a valid image file.'}), 400

        # Save and process the question image
        question_filename = secure_filename(question_image.filename)
        question_file_path = os.path.join(app.config['UPLOAD_FOLDER'], question_filename)
        question_image.save(question_file_path)
        logger.info(f"Saved uploaded question image to {question_file_path}")

        with open(question_file_path, "rb") as image_file:
            encoded_question_image = base64.b64encode(image_file.read()).decode('utf-8')

        # Save and process the answer image
        answer_filename = secure_filename(answer_image.filename)
        answer_file_path = os.path.join(app.config['UPLOAD_FOLDER'], answer_filename)
        answer_image.save(answer_file_path)
        logger.info(f"Saved uploaded answer image to {answer_file_path}")

        with open(answer_file_path, "rb") as image_file:
            encoded_answer_image = base64.b64encode(image_file.read()).decode('utf-8')

        # Extract text from images using Sambanova API
        question_text = extract_text_from_image(encoded_question_image, question_filename, "question")
        answer_text = extract_text_from_image(encoded_answer_image, answer_filename, "answer")

        # Optionally, delete the uploaded images after processing
        os.remove(question_file_path)
        os.remove(answer_file_path)
        logger.info(f"Deleted uploaded image files after processing.")

        # Final evaluation using OpenAI
        final_evaluation, total_score = evaluate_using_openai(question_text, answer_text)

        return jsonify({
            'evaluation': final_evaluation,
            'score': total_score
        }), 200

    except requests.exceptions.RequestException as e:
        logger.error(f"Request exception: {str(e)}")
        return jsonify({'error': f"Request exception: {str(e)}"}), 502
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        return jsonify({'error': f"Server error: {str(e)}"}), 500


def extract_text_from_image(encoded_image, filename, context):
    """Extract text from an image using Sambanova AI."""
    payload_image = {
        "stream": False,
        "model": "Llama-3.2-11B-Vision-Instruct",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Extract the {context} text from the following image."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{filename.rsplit('.',1)[1].lower()};base64,{encoded_image}"
                        }
                    }
                ]
            }
        ]
    }

    headers_image = {
        "Authorization": f"Bearer {SAMBANOVA_API_KEY}",
        "Content-Type": "application/json"
    }

    logger.info(f"Sending {context} image to Sambanova AI API for text extraction.")
    response = requests.post(
        SAMBANOVA_CHAT_API_URL,
        json=payload_image,
        headers=headers_image
    )

    if response.status_code != 200:
        logger.error(f"Sambanova API error during {context} image processing: {response.status_code} - {response.text}")
        raise Exception(f"Sambanova API error during {context} image processing: {response.text}")

    json_response = response.json()
    try:
        extracted_text = json_response['choices'][0]['message']['content'].strip()
        logger.info(f"Extracted {context} text from image successfully.")
        return extracted_text
    except (KeyError, IndexError):
        logger.error(f"Unexpected response structure from Sambanova API during {context} image processing.")
        logger.debug(f"Sambanova API Response: {json_response}")
        raise Exception("Unexpected response structure from Sambanova API.")

def evaluate_using_openai(question_text, answer_text):
    """Evaluate the answer using OpenAI's API."""
    openai.api_key = os.getenv("OPENAI_API_KEY")

    evaluation_prompt = (
        f"As an experienced educator, evaluate the student's answer to the following question. "
        f"Provide detailed feedback on the correctness, completeness, clarity, and areas for improvement. "
        f"Assign a score out of 10 for the answer.\n\n"
        f"Question:\n{question_text}\n\n"
        f"Student's Answer:\n{answer_text}\n\n"
        f"Feedback and Score:"
    )

    try:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=evaluation_prompt,
            max_tokens=300
        )

        evaluation = response['choices'][0]['text'].strip()
        logger.info("Final evaluation completed using OpenAI.")

        # Extract score from evaluation text (assumes score is mentioned as "Score: X/10")
        match = re.search(r"Score:\s*(\d+)/10", evaluation)
        total_score = int(match.group(1)) if match else None

        return evaluation, total_score

    except openai.error.OpenAIError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise Exception(f"OpenAI API error: {str(e)}")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  
    app.run(host='0.0.0.0', port=port)
