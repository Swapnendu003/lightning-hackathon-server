# Article Generator API

A Flask-based API for generating articles using Sambanova AI, with Swagger documentation.

## Features

- Generates articles based on a given topic.
- Integrated with Sambanova AI for content generation.
- Swagger documentation for easy API exploration.

---

## Prerequisites

Make sure you have the following installed on your system:

1. Python (>= 3.9)
2. pip (Python package manager)
3. [Sambanova API key](https://api.sambanova.ai) (to use the external API)

---

## Setup Instructions

Follow these steps to set up and run the project locally.

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/your-repository-name.git
cd your-repository-name
```

### 2. Create a Virtual Environment

Create and activate a virtual environment to isolate dependencies:

```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

Create a `.env` file in the root of your project and add the following:

```plaintext
SAMBANOVA_API_KEY=your_sambanova_api_key
```

Replace `your_sambanova_api_key` with your actual Sambanova API key.

---

## Running the Application

Start the Flask application:

```bash
python app.py
```

By default, the app will run on `http://localhost:5000`.

---

## Access Swagger Documentation

Once the app is running, you can access the Swagger documentation at:

```
http://localhost:5000/swagger/
```

This provides an interactive API interface to test endpoints.

---

## API Endpoints

### 1. `GET /`

**Description:** Home route that returns a welcome message.

**Response:**

```json
{
  "message": "Welcome to the Article Generator API!"
}
```

---

### 2. `POST /generate-article`

**Description:** Generates an article based on the given topic.

**Request Body:**

```json
{
  "topic": "Artificial Intelligence in Healthcare"
}
```

**Response:**

```json
{
  "article": "Artificial intelligence (AI) is transforming the healthcare industry by enabling faster diagnosis..."
}
```

---

## Testing Locally

You can use tools like [Postman](https://www.postman.com/) or `curl` to test the API.

### Example with `curl`:

```bash
curl -X POST http://localhost:5000/generate-article \
-H "Content-Type: application/json" \
-d '{"topic": "Artificial Intelligence in Healthcare"}'
```

---

## Common Issues

### 1. `ModuleNotFoundError`
If you encounter a `ModuleNotFoundError`, ensure all dependencies are installed with:
```bash
pip install -r requirements.txt
```

### 2. Missing API Key
Ensure your `.env` file contains the correct `SAMBANOVA_API_KEY`.

### 3. Port Already in Use
If you encounter a port conflict, change the port in `app.py`:
```python
app.run(host='0.0.0.0', port=your_port)
```
