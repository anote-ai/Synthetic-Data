# Anote Synthetic Data API Server

This is the backend API server for the Anote Synthetic Data platform.

## Setup Instructions

### 1. Install Dependencies

```bash
# Navigate to the server directory
cd server

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the server directory with the following variables:

```env
# OpenAI API Key for text generation
OPENAI_API_KEY=your_openai_api_key_here

# Database configuration (if using a database)
DATABASE_URL=sqlite:///anote_synthetic_data.db

# JWT Secret for token verification (in production, use a strong secret)
JWT_SECRET=your_jwt_secret_here

# API configuration
API_KEY=your_api_key_here
```

### 3. Run the Server

#### Option 1: Using the run script (Recommended)
```bash
python run.py
```

#### Option 2: Using Flask directly
```bash
# Set Flask environment variables
set FLASK_APP=app.py
set FLASK_ENV=development

# Run Flask
flask run --host=0.0.0.0 --port=5000
```

### 4. Test the API

The server will be available at:
- **Base URL**: http://localhost:5000
- **API Endpoint**: http://localhost:5000/public/generate

#### Example API Request:
```bash
curl -X POST http://localhost:5000/public/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_jwt_token_here" \
  -d '{
    "task_type": "text",
    "prompt": "Generate customer reviews for a restaurant",
    "num_rows": 10,
    "columns": ["review", "rating", "customer_name"]
  }'
```

## API Endpoints

### POST /public/generate

Generates synthetic data based on the provided parameters.

**Request Body:**
```json
{
  "task_type": "text|image|video",
  "prompt": "Description of data to generate",
  "num_rows": 10,
  "columns": ["column1", "column2"],
  "examples": []
}
```

**Response:**
```json
{
  "data": "Generated synthetic data"
}
```

## Supported Task Types

- **text**: Generate synthetic text datasets using OpenAI
- **image**: Generate synthetic image data
- **video**: Generate synthetic video content

## Development

- The server runs in debug mode by default
- Changes to Python files will automatically reload the server
- Check the console for any error messages 