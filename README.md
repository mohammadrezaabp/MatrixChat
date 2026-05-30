# Matrix Chat

A stunning Matrix-styled chat application that connects to Llama 3.2 running locally via Ollama. Pure green-on-black terminal aesthetic with glitch effects.

![Matrix Chat Screenshot](./docs/screenshot.png)

## Features

✨ **Matrix Aesthetics**
- Classic green-on-black color scheme (#00ff00 on black)
- Monospace font throughout
- Glitch effects on the header
- Terminal-style UI elements with borders

🚀 **Full-Stack Architecture**
- **Frontend**: Next.js 16 with React 19
- **Backend**: FastAPI Python service
- **Model**: Llama 3.2 via local Ollama
- **Communication**: REST API

💬 **Chat Capabilities**
- Real-time message streaming
- Conversation history context
- Adjustable temperature & top_p parameters
- Error handling with helpful messages

🔧 **Easy Deployment**
- Local development setup
- Docker Compose for containerized setup
- Simple environment configuration
- Health check endpoints

## Quick Start

See [QUICKSTART.md](./QUICKSTART.md) for a 5-minute setup guide.

### TL;DR

```bash
# Terminal 1: Backend
cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt && python main.py

# Terminal 2: Frontend
pnpm install && pnpm dev

# Open: http://localhost:3000
```

## Architecture

### Frontend (Next.js)
- **Port**: 3000
- **Framework**: Next.js 16 with App Router
- **Styling**: Tailwind CSS with custom Matrix colors
- **Components**: ChatMessage, ChatInput, main chat page
- **API Client**: Fetch API to backend

### Backend (FastAPI)
- **Port**: 8000
- **Framework**: FastAPI with async/await
- **Database**: None (stateless API)
- **AI**: Ollama API client
- **CORS**: Configured for localhost:3000

### LLM (Ollama)
- **Port**: 11434
- **Model**: Llama 3.2
- **Deployment**: Docker container
- **Connection**: HTTP API

## Setup Detailed Guide

See [SETUP.md](./SETUP.md) for comprehensive setup instructions including:
- Docker Ollama setup
- Python environment configuration
- Frontend installation
- Environment variable configuration
- Troubleshooting

## Project Structure

```
matrix-chat/
├── app/
│   ├── page.tsx                 # Main chat page with chat logic
│   ├── layout.tsx               # Root layout with dark mode
│   └── globals.css              # Matrix colors, animations, glitch effects
│
├── components/
│   ├── chat-message.tsx         # Message display component
│   └── chat-input.tsx           # Input field component
│
├── backend/
│   ├── main.py                  # FastAPI server with /chat endpoint
│   ├── requirements.txt          # Python dependencies
│   ├── .env.example             # Environment template
│   └── Dockerfile               # Container image
│
├── public/                       # Static assets
├── .env.local                   # Frontend env vars
├── docker-compose.yml           # Multi-container setup
├── QUICKSTART.md                # 5-minute setup
├── SETUP.md                     # Detailed guide
└── README.md                    # This file
```

## Configuration

### Frontend (.env.local)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Backend (backend/.env)

```env
OLLAMA_API_URL=http://localhost:11434
MODEL_NAME=llama3.2
```

Update `OLLAMA_API_URL` if running Ollama in Docker:
- Local: `http://localhost:11434`
- Docker: `http://host.docker.internal:11434`

## API Endpoints

### POST /chat

Send a message and get a response.

**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi!"}
  ],
  "model": "llama3.2",
  "temperature": 0.7,
  "top_p": 0.9
}
```

**Response:**
```json
{
  "response": "Your response here",
  "model": "llama3.2"
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{"status": "ok"}
```

## Color Palette

| Element | Color | Hex |
|---------|-------|-----|
| Background | Black | `#000000` |
| Primary Text | Bright Green | `#00ff00` |
| Secondary Text | Darker Green | `#00cc00` |
| Muted Text | Dark Green | `#003300` |
| Input Background | Very Dark Green | `#001100` |
| Borders | Green | `#003300` |

## Custom Styles

Matrix theme CSS is defined in `app/globals.css`:

- **Color variables**: CSS custom properties for the theme
- **Glitch animations**: Authentic Matrix text effects
- **Matrix-specific utilities**: Tailwind component classes
- **Dark mode only**: Always dark, no light mode

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Send message | ENTER |
| New line | SHIFT + ENTER |
| Focus input | Click textarea |

## Performance

- **First response**: 10-30 seconds (model loading on first call)
- **Subsequent responses**: 5-15 seconds
- **Token limit**: Depends on Llama 3.2 context window
- **Streaming**: Available via `/stream-chat` endpoint (frontend doesn't use it yet)

## Troubleshooting

### Connection Issues

**"Cannot connect to Ollama"**
- Verify Docker: `docker ps | grep ollama`
- Check endpoint: `curl http://localhost:11434/api/tags`
- Restart container: `docker restart ollama`

**"API error" in chat**
- Check backend logs for errors
- Verify `.env` files are configured
- Test health endpoint: `curl http://localhost:8000/health`

**CORS errors**
- Confirm `NEXT_PUBLIC_API_URL` in `.env.local`
- Check backend CORS configuration in `main.py`
- Try from same localhost port

### Performance Issues

**Slow responses**
- Llama 3.2 is CPU-bound; GPU helps significantly
- First response loads the model (~4GB)
- Reduce context by clearing chat history
- Lower context window in backend if needed

**Out of memory**
- Llama 3.2 requires ~4GB RAM
- Close other applications
- Use GPU support if available

## Development

### Adding Features

1. **New components**: Create in `components/`
2. **API endpoints**: Add to `backend/main.py`
3. **Styles**: Update `app/globals.css`
4. **Types**: Define interfaces at component top

### Testing

```bash
# Frontend
pnpm lint
pnpm type-check

# Backend
pytest backend/
```

### Deployment

See [SETUP.md](./SETUP.md) for Docker Compose deployment instructions.

## Tech Stack

- **Frontend**: Next.js 16, React 19, Tailwind CSS
- **Backend**: FastAPI, Pydantic, HTTPx
- **Runtime**: Node.js 18+, Python 3.8+
- **Containerization**: Docker, Docker Compose
- **AI**: Ollama, Llama 3.2

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (responsive design)

## Future Enhancements

- [ ] Streaming response tokens
- [ ] Conversation saving/loading
- [ ] Multiple model selection
- [ ] Custom system prompts
- [ ] Voice input/output
- [ ] Rate limiting & throttling
- [ ] User authentication
- [ ] SQLite conversation history

## Contributing

Feel free to fork, modify, and improve! Some ideas:
- Add more Matrix visual effects
- Implement streaming responses
- Add authentication layer
- Create conversation management UI
- Add dark mode toggle (jk, always dark)

## License

MIT - Use freely for personal and commercial projects.

## Support

Having issues? Check these in order:

1. [QUICKSTART.md](./QUICKSTART.md) - Quick setup
2. [SETUP.md](./SETUP.md) - Detailed guide
3. [Troubleshooting section](#troubleshooting) above
4. GitHub Issues (if this were on GitHub)

---

**Welcome to the Matrix.** Your choice to take the green pill was wise. 🟢

```
    ᚛ ᚜ ᚛ ᚜ ᚛ ᚜ ᚛ ᚜ ᚛ ᚜
   ᚛ ᚜ ᚛ ᚜ ᚛ ᚜ ᚛ ᚜ ᚛ ᚜ ᚛
  ᚛ ᚜ ᚛ ᚜ ᚛ ᚜ ᚛ ᚜ ᚛ ᚜ ᚛ ᚜
```
