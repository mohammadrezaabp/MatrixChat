# Matrix Chat - Setup Guide

A Matrix-styled chat application that connects to Llama 3.2 running locally via Ollama.

## Architecture

- **Frontend**: Next.js 16 (Port 3000) - Matrix-themed UI with green text and glitch effects
- **Backend**: FastAPI Python service (Port 8000) - Connects to local Ollama
- **Model**: Llama 3.2 running in Docker via Ollama

## Prerequisites

- Docker Desktop running with Ollama image (`docker run -d -p 11434:11434 ollama/ollama`)
- Llama 3.2 model pulled: `docker exec <container-id> ollama pull llama3.2`
- Node.js 18+ installed
- Python 3.8+ installed

## Setup Instructions

### 1. Start Ollama in Docker

```bash
# If not already running, start the Ollama container
docker run -d -p 11434:11434 --name ollama ollama/ollama

# Pull the Llama 3.2 model (if not already done)
docker exec ollama ollama pull llama3.2

# Verify it's running
curl http://localhost:11434/api/tags
```

### 2. Setup Python Backend

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file (if not already created)
cp .env.example .env

# Start the FastAPI server
python main.py
```

The backend will be available at `http://localhost:8000`

**Health check:**
```bash
curl http://localhost:8000/health
```

### 3. Setup Next.js Frontend

```bash
# In the project root directory
pnpm install
# or
npm install

# Start the dev server
pnpm dev
# or
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Usage

1. Navigate to `http://localhost:3000` in your browser
2. You'll see the Matrix Chat interface with a welcome message
3. Type your message in the input field at the bottom
4. Press ENTER to send (or click SEND button)
5. The app will connect to your local Llama 3.2 model and return a response

## Environment Variables

### Frontend (.env.local)
- `NEXT_PUBLIC_API_URL` - Backend API URL (default: http://localhost:8000)

### Backend (backend/.env)
- `OLLAMA_API_URL` - Ollama API endpoint (default: http://host.docker.internal:11434)
- `MODEL_NAME` - Model to use (default: llama3.2)

**Note on Docker:** If you're running the Python backend inside Docker, use `http://host.docker.internal:11434`. If running locally, use `http://localhost:11434`.

## Features

- **Matrix Aesthetic**: Green text on black background with monospace font
- **Glitch Effects**: Random glitch animations on the header
- **Message History**: Maintains conversation context with the model
- **Real-time Updates**: Instant message display and response handling
- **Error Handling**: Clear error messages if backend/Ollama is unavailable
- **Responsive Design**: Works on mobile and desktop

## Troubleshooting

### "Cannot connect to Ollama"
- Verify Docker container is running: `docker ps | grep ollama`
- Check Ollama is pulling models correctly: `docker logs ollama`
- Try the health endpoint: `curl http://localhost:11434/api/tags`

### "API error" in chat
- Ensure FastAPI backend is running on port 8000
- Check backend terminal for error messages
- Verify `.env` file is configured correctly in the `backend/` directory

### CORS errors
- Confirm `NEXT_PUBLIC_API_URL` in `.env.local` matches your backend URL
- Backend CORS is configured for `http://localhost:3000` and `http://localhost:3001`

### Model not found
- Verify Llama 3.2 is pulled: `docker exec ollama ollama list`
- Update `MODEL_NAME` in `backend/.env` if using a different model

## API Endpoints

### POST /chat
Send a message and get a response.

Request:
```json
{
  "messages": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"}
  ],
  "model": "llama3.2",
  "temperature": 0.7,
  "top_p": 0.9
}
```

Response:
```json
{
  "response": "Your response here",
  "model": "llama3.2"
}
```

### GET /health
Simple health check endpoint.

Response:
```json
{"status": "ok"}
```

## Performance Notes

- First response may take 10-30 seconds depending on your hardware
- Llama 3.2 is optimized for performance, especially on CPU
- Consider using GPU for faster responses if available
- Adjust `temperature` and `top_p` parameters for different response styles

## Stopping Services

```bash
# Stop Next.js (Ctrl+C in terminal)

# Stop FastAPI (Ctrl+C in terminal)

# Stop Ollama Docker container
docker stop ollama

# Deactivate Python venv
deactivate
```

## Future Enhancements

- Streaming responses for real-time text generation
- Conversation management (save/load chats)
- Multiple model selection
- Custom system prompts
- Voice input/output
- Rate limiting and authentication

---

Enjoy chatting with the Matrix!
