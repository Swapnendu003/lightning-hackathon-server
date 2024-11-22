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

load_dotenv()

app = Flask(__name__)
CORS(app)

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
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
    "host": "lightning-hackathon-server.onrender.com",
    "basePath": "/",
    "schemes": ["https"],
}
Swagger(app, config=swagger_config, template=swagger_template)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

SAMBANOVA_API_KEY = os.getenv("SAMBANOVA_API_KEY")
SAMBANOVA_CHAT_API_URL = "https://api.sambanova.ai/v1/chat/completions"
MAX_TOKENS = 16384
RESERVED_TOKENS = 1000
MAX_SYLLABUS_TOKENS = MAX_TOKENS - RESERVED_TOKENS
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
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
    try:
        data = request.get_json()
        if not data or 'topic' not in data:
            logger.warning("No topic provided.")
            return jsonify({'error': 'No topic provided'}), 400
        topic = data['topic'].strip()
        if not topic:
            logger.warning("Empty topic provided.")
            return jsonify({'error': 'Empty topic provided'}), 400

        payload = {
            "stream": False,
            "model": "Meta-Llama-3.1-8B-Instruct",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a highly knowledgeable assistant specialized in engineering and technical subjects. "
                        "Respond to technical topics with clear, understandable, and example-rich articles."
                    )
                },
                {
                    "role": "user",
                    "content": f"Generate an article about {topic}."
                }
            ]
        }

        headers = {
            "Authorization": f"Bearer {SAMBANOVA_API_KEY}",
            "Content-Type": "application/json"
        }

        logger.info(f"Requesting article for topic: {topic}")
        response = requests.post(
            SAMBANOVA_CHAT_API_URL,
            json=payload,
            headers=headers,
            stream=payload.get("stream", False)
        )

        if response.status_code != 200:
            logger.error(f"Sambanova API error: {response.status_code} - {response.text}")
            return jsonify({'error': f"Sambanova API error: {response.text}"}), response.status_code

        if payload.get("stream", False):
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
            return Response(generate(), mimetype='text/event-stream')
        else:
            json_response = response.json()
            try:
                article = json_response['choices'][0]['message']['content'].strip()
                logger.info(f"Article generated for topic: {topic}")
            except (KeyError, IndexError):
                logger.error("Unexpected Sambanova API response structure.")
                logger.debug(f"Response: {json_response}")
                return jsonify({'error': 'Unexpected response structure from Sambanova API.'}), 502
            return jsonify({'article': article}), 200

    except requests.exceptions.RequestException as e:
        logger.error(f"Request exception: {str(e)}")
        return jsonify({'error': f"Request exception: {str(e)}"}), 502
    except Exception as e:
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
    try:
        syllabus_text = None
        syllabus_image_present = False
        syllabus_text_present = False

        content_type = request.content_type
        logger.debug(f"Content-Type: {content_type}")

        if 'multipart/form-data' in content_type:
            syllabus_image = request.files.get('syllabus_image')
            syllabus_text_field = request.form.get('syllabus_text')

            if syllabus_image and syllabus_text_field:
                return jsonify({'error': 'Provide either syllabus_text or syllabus_image, not both.'}), 400
            elif syllabus_image:
                syllabus_image_present = True
            elif syllabus_text_field:
                syllabus_text_present = True
                syllabus_text = syllabus_text_field.strip()
            else:
                return jsonify({'error': 'No syllabus_text or syllabus_image provided.'}), 400

        elif 'application/json' in content_type:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Empty JSON payload.'}), 400

            syllabus_text_field = data.get('syllabus_text')
            if 'syllabus_image' in data:
                return jsonify({'error': 'syllabus_image should be uploaded as a file, not in JSON payload.'}), 400
            if syllabus_text_field:
                syllabus_text_present = True
                syllabus_text = syllabus_text_field.strip()

            if not syllabus_text_present:
                return jsonify({'error': 'No syllabus_text provided.'}), 400
        else:
            return jsonify({'error': 'Unsupported Content-Type. Use multipart/form-data or application/json.'}), 400

        if syllabus_image_present:
            file: FileStorage = request.files['syllabus_image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                with open(file_path, "rb") as image_file:
                    encoded_image = base64.b64encode(image_file.read()).decode('utf-8')

                payload_image = {
                    "stream": False,
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

                response_image = requests.post(
                    SAMBANOVA_CHAT_API_URL,
                    json=payload_image,
                    headers=headers_image,
                    stream=payload_image.get("stream", False)
                )

                if response_image.status_code != 200:
                    return jsonify({'error': f"Sambanova API error during image processing: {response_image.text}"}), response_image.status_code

                json_response_image = response_image.json()
                try:
                    syllabus_text = json_response_image['choices'][0]['message']['content'].strip()
                except (KeyError, IndexError):
                    return jsonify({'error': 'Unexpected response structure from Sambanova API during image processing.'}), 502

                os.remove(file_path)
            else:
                return jsonify({'error': 'Invalid or no file uploaded. Please upload a valid image file.'}), 400
        elif syllabus_text_present:
            if not syllabus_text:
                return jsonify({'error': 'Empty syllabus_text provided.'}), 400

        # Updated prompt
        prompt = (
            f"You are an educational assistant tasked with generating exam questions. "
            f"Based on the following syllabus, generate exactly 5 short (multiple-choice or short-answer) questions and exactly 5 descriptive (essay or open-ended) questions. "
            f"Please ensure your response is in valid JSON format with the specified structure.\n\n"
            f"Syllabus:\n{syllabus_text}\n\n"
            f"Response Format:\n"
            f"{{\n"
            f'    "short_questions": ["Short Question 1", "Short Question 2", "Short Question 3", "Short Question 4", "Short Question 5"],\n'
            f'    "descriptive_questions": ["Descriptive Question 1", "Descriptive Question 2", "Descriptive Question 3", "Descriptive Question 4", "Descriptive Question 5"]\n'
            f"}}"
        )

        payload_questions = {
            "stream": False,
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

        response_questions = requests.post(
            SAMBANOVA_CHAT_API_URL,
            json=payload_questions,
            headers=headers_questions,
            stream=payload_questions.get("stream", False)
        )

        if response_questions.status_code != 200:
            return jsonify({'error': f"Sambanova API error during question generation: {response_questions.text}"}), response_questions.status_code

        json_response_questions = response_questions.json()
        try:
            questions_text = json_response_questions['choices'][0]['message']['content'].strip()
            logger.debug(f"AI Response Content:\n{questions_text}")

            # Extract JSON using regex
            json_match = re.search(r'\{.*\}', questions_text, re.DOTALL)
            if json_match:
                questions_json = json.loads(json_match.group())
            else:
                return jsonify({'error': 'No JSON object found in AI response.'}), 502

            short_questions = questions_json.get('short_questions', [])
            descriptive_questions = questions_json.get('descriptive_questions', [])

            # Handle cases where AI might have returned all questions in one list
            if not descriptive_questions and len(short_questions) >= 10:
                descriptive_questions = short_questions[5:]
                short_questions = short_questions[:5]

            # Ensure both lists have 5 questions
            if len(short_questions) < 5 or len(descriptive_questions) < 5:
                logger.error("Insufficient questions generated.")
                return jsonify({'error': 'Insufficient questions generated. Please try again.'}), 502

        except json.JSONDecodeError as e:
            logger.error(f"JSON decoding error: {str(e)}")
            return jsonify({'error': 'Failed to parse JSON from AI response.'}), 502
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return jsonify({'error': 'An unexpected error occurred while processing the AI response.'}), 500

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
    try:
        if 'question_image' not in request.files or 'answer_image' not in request.files:
            return jsonify({'error': 'Both question_image and answer_image must be provided.'}), 400

        question_image = request.files['question_image']
        answer_image = request.files['answer_image']

        if not (question_image and allowed_file(question_image.filename)):
            return jsonify({'error': 'Invalid or no question_image uploaded. Please upload a valid image file.'}), 400
        if not (answer_image and allowed_file(answer_image.filename)):
            return jsonify({'error': 'Invalid or no answer_image uploaded. Please upload a valid image file.'}), 400

        question_filename = secure_filename(question_image.filename)
        question_file_path = os.path.join(app.config['UPLOAD_FOLDER'], question_filename)
        question_image.save(question_file_path)
        with open(question_file_path, "rb") as image_file:
            encoded_question_image = base64.b64encode(image_file.read()).decode('utf-8')

        answer_filename = secure_filename(answer_image.filename)
        answer_file_path = os.path.join(app.config['UPLOAD_FOLDER'], answer_filename)
        answer_image.save(answer_file_path)
        with open(answer_file_path, "rb") as image_file:
            encoded_answer_image = base64.b64encode(image_file.read()).decode('utf-8')

        question_text = extract_text_from_image(encoded_question_image, question_filename, "question")
        answer_text = extract_text_from_image(encoded_answer_image, answer_filename, "answer")

        os.remove(question_file_path)
        os.remove(answer_file_path)

        final_evaluation, total_score = evaluate_using_openai(question_text, answer_text)

        return jsonify({
            'evaluation': final_evaluation,
            'score': total_score
        }), 200

    except requests.exceptions.RequestException as e:
        return jsonify({'error': f"Request exception: {str(e)}"}), 502
    except Exception as e:
        return jsonify({'error': f"Server error: {str(e)}"}), 500

def extract_text_from_image(encoded_image, filename, context):
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

    response = requests.post(
        SAMBANOVA_CHAT_API_URL,
        json=payload_image,
        headers=headers_image
    )

    if response.status_code != 200:
        raise Exception(f"Sambanova API error during {context} image processing: {response.text}")

    json_response = response.json()
    try:
        extracted_text = json_response['choices'][0]['message']['content'].strip()
        return extracted_text
    except (KeyError, IndexError):
        raise Exception("Unexpected response structure from Sambanova API.")

def evaluate_using_openai(question_text, answer_text):
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
        match = re.search(r"Score:\s*(\d+)/10", evaluation)
        total_score = int(match.group(1)) if match else None
        return evaluation, total_score
    except openai.error.OpenAIError as e:
        raise Exception(f"OpenAI API error: {str(e)}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  
    app.run(host='0.0.0.0', port=port)
