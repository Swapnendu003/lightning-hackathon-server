```markdown
# 📚 Prepify Backend

[![GitHub](https://img.shields.io/github/license/Swapnendu003/lightning-hackathon-server)](https://github.com/Swapnendu003/lightning-hackathon-server/blob/main/LICENSE)
[![Swagger Documentation](https://img.shields.io/badge/Swagger-Docs-blue)](https://lightning-hackathon-server.onrender.com/swagger/)
[![Hosted Backend](https://img.shields.io/badge/Hosted%20Backend-Online-green)](https://lightning-hackathon-server.onrender.com)

## 🚀 Overview

**Prepify Backend** is a Flask-based API server designed to revolutionize the educational experience by leveraging **Artificial Intelligence (AI)** and **3D technologies**. Powered by **SambaNova Cloud**, Prepify offers functionalities such as article generation, question bank creation, and automated answer evaluation. The backend seamlessly integrates advanced AI models to provide personalized and efficient educational tools for students and educators alike.

## 🌟 Features

- **Article Generation:** Create comprehensive articles on technical topics using AI.
- **Question Bank Generation:** Generate a diverse set of short and descriptive questions based on provided syllabi (text or image).
- **Automated Answer Evaluation:** Evaluate student answers by analyzing answer images against question images, providing detailed feedback and scores.
- **Optical Character Recognition (OCR):** Extract text from handwritten answer scripts with high accuracy using AI-powered OCR.
- **API Documentation:** Interactive API documentation available via Swagger UI.

## 🔧 Technologies Used

- **Backend Framework:** Flask
- **API Documentation:** Flasgger (Swagger UI)
- **CORS Handling:** Flask-CORS
- **Environment Management:** Python-dotenv
- **Logging:** Python's `logging` module
- **AI Integration:** SambaNova AI Models
  - **OCR:** `Llama-3.2-11B-Vision-Instruct`
  - **Text Processing & Evaluation:** `Meta-Llama-3.1-8B-Instruct`
- **Deployment:** Hosted on [Render](https://render.com/)

## 📦 Getting Started

### Prerequisites

- **Python 3.7+**
- **Pip** (Python package installer)
- **SambaNova API Key:** Obtain from [SambaNova Systems](https://sambanova.ai/)

### Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/Swapnendu003/lightning-hackathon-server.git
   cd lightning-hackathon-server
   ```

2. **Create a Virtual Environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows, use venv\Scripts\activate
   ```

3. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set Up Environment Variables**

   Create a `.env` file in the root directory and add the following:

   ```env
   SAMBANOVA_API_KEY=your_sambanova_api_key
   ```


### Running the Server

```bash
python app.py
```

The server will start on `http://0.0.0.0:5000/` by default.

## 🌐 Hosted Backend

Access the live backend API at: [https://lightning-hackathon-server.onrender.com](https://lightning-hackathon-server.onrender.com)

## 📄 API Documentation

Interactive API documentation is available via Swagger UI:

[https://lightning-hackathon-server.onrender.com/swagger/](https://lightning-hackathon-server.onrender.com/swagger/)

## 📋 API Endpoints

### 1. Home

- **URL:** `/`
- **Method:** `GET`
- **Description:** Welcome message.
- **Response:**
  - `200 OK` with message `"Welcome to the Article and Question Generator API!"`

### 2. Generate Article

- **URL:** `/generate-article`
- **Method:** `POST`
- **Description:** Generate an article based on a given technical topic using SambaNova AI.
- **Parameters:**
  - `topic` (string, required): The technical topic for the article.
- **Responses:**
  - `200 OK`: Returns the generated article.
  - `400 Bad Request`: Missing or invalid input.
  - `502 Bad Gateway`: Error communicating with SambaNova AI API.
  - `500 Internal Server Error`: Server-side error.

### 3. Generate Questions

- **URL:** `/generate-questions`
- **Method:** `POST`
- **Description:** Generate up to 10 questions (5 short and 5 descriptive) based on a provided syllabus. The syllabus can be provided either as text or as an uploaded image. **Provide either `syllabus_text` or `syllabus_image` in a single request, not both.**
- **Parameters:**
  - `syllabus_text` (string, optional): Text of the syllabus.
  - `syllabus_image` (file, optional): Image file of the syllabus.
- **Responses:**
  - `200 OK`: Returns generated short and descriptive questions.
  - `400 Bad Request`: Missing or invalid input.
  - `502 Bad Gateway`: Error communicating with SambaNova AI API.
  - `500 Internal Server Error`: Server-side error.

### 4. Evaluate Answer

- **URL:** `/evaluate-answer`
- **Method:** `POST`
- **Description:** Evaluate a student's answer to a given question. Both the question and the answer should be provided as images.
- **Parameters:**
  - `question_image` (file, required): Image file of the question.
  - `answer_image` (file, required): Image file of the student's answer.
- **Responses:**
  - `200 OK`: Returns the evaluation feedback and score.
  - `400 Bad Request`: Missing or invalid input.
  - `502 Bad Gateway`: Error communicating with SambaNova AI API.
  - `500 Internal Server Error`: Server-side error.

## 🛠️ Deployment

The backend is hosted on [Render](https://render.com/), ensuring scalability and reliability. Continuous deployment is set up via GitHub, so any push to the main branch will automatically deploy the latest version.
# 📈 Conclusion

**Prepify Backend** leverages the power of **SambaNova Systems** and **Azure Speech SDK** to transform the educational landscape. By integrating advanced AI and 3D technologies, Prepify provides an engaging, efficient, and personalized learning experience that caters to the diverse needs of students and educators alike.

---
```
