# Matrix Chat - Quick Start

Get your Matrix Chat running in 5 minutes!

## Prerequisites Checklist

- Docker Desktop running
- Node.js 18+ installed
- Python 3.8+ installed
- Llama 3.2 model already pulled in Docker Ollama

## Option 1: Local Development (Recommended for Testing)

### Step 1: Start Ollama

```bash
# Ensure Ollama Docker container is running
docker ps | grep ollama  # Should show a running container

# If not running:
docker run -d -p 11434:11434 --name ollama ollama/ollama
docker exec ollama ollama pull llama3.2
```

### Step 2: Start Python Backend

```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
python main.py
```

You should see:
```
Uvicorn running on http://0.0.0.0:8000
```

### Step 3: Start Next.js Frontend (New Terminal)

```bash
pnpm install
pnpm dev
```

You should see:
```
Local:        http://localhost:3000
```

### Step 4: Open in Browser

Go to **http://localhost:3000** and start chatting!

---

## Option 2: Docker Compose (Simplified)

One command to start everything:

```bash
docker-compose up
```

This starts:
- Ollama on port 11434
- Python backend on port 8000
- You still run Next.js locally on port 3000

```bash
# In another terminal
pnpm install
pnpm dev
```

---

## Testing the Connection

### 1. Check Ollama

```bash
curl http://localhost:11434/api/tags
```

Should return a list of models including `llama3.2`

### 2. Check Backend Health

```bash
curl http://localhost:8000/health
```

Should return:
```json
{"status": "ok"}
```

### 3. Test Chat API

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello"}],
    "model": "llama3.2"
  }'
```

Should return a response from Llama.

---

## First Chat

1. Type: `"What is the Matrix?"`
2. Press ENTER
3. Wait for response (first response takes 10-30s)
4. Enjoy the Matrix experience!

---

## Troubleshooting

### Port Already in Use

```bash
# Find what's using the port
# Windows:
netstat -ano | findstr :3000

# Mac/Linux:
lsof -i :3000

# Kill the process (replace PID with actual process ID)
kill -9 <PID>
```

### Ollama Connection Error

- Verify Docker container: `docker ps | grep ollama`
- Check logs: `docker logs ollama`
- Restart: `docker restart ollama`

### Backend Not Responding

- Check terminal for error messages
- Verify Python venv is activated
- Try: `python -c "import fastapi"` to test imports

### Frontend Not Loading

- Verify Node.js: `node --version` (should be 18+)
- Clear cache: Delete `.next` folder
- Reinstall: `pnpm install`

---

## Performance Tips

- **First response**: 10-30 seconds (model loading)
- **Subsequent responses**: 5-15 seconds
- **GPU acceleration**: Much faster if using NVIDIA GPU in Docker
- **Adjust temperature**: Lower = more deterministic, higher = more creative

---

## Next Steps

1. **Customize the prompt**: Edit the system message in `app/page.tsx`
2. **Change the model**: Update `MODEL_NAME` in `backend/.env`
3. **Adjust styling**: Modify colors in `app/globals.css`
4. **Add features**: See API endpoints in `SETUP.md`

---

## File Structure

```
.
├── app/                          # Next.js frontend
│   ├── page.tsx                 # Main chat page
│   ├── layout.tsx               # App layout
│   └── globals.css              # Matrix styling & animations
├── components/                   # React components
│   ├── chat-message.tsx         # Message display
│   └── chat-input.tsx           # Input field
├── backend/                      # Python FastAPI
│   ├── main.py                  # API server
│   ├── requirements.txt          # Python dependencies
│   ├── Dockerfile              # Docker image
│   └── .env.example            # Config template
├── docker-compose.yml           # Docker setup
├── SETUP.md                     # Detailed setup guide
└── QUICKSTART.md                # This file
```

---

Enjoy your Matrix Chat! Type `/help` for... just kidding, it doesn't exist yet. But it's a fun idea!
