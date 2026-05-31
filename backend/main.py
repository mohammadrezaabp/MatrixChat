from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
from typing import Optional
import re

app = FastAPI()

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://host.docker.internal:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "llama3.2")
SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "MySqlSchema.sql")

CHAT_SYSTEM_PROMPT = (
    "You are a helpful English-language assistant. Reply in clear, natural English. "
    "Keep answers concise unless the user asks for more detail."
)

SQL_SYSTEM_PROMPT = (
    "You are a helpful English-language assistant that converts natural language requests into valid MySQL. "
    "Return only the SQL query and nothing else."
)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: Optional[str] = MODEL_NAME
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9

class ChatResponse(BaseModel):
    response: str
    model: str

class TextToSqlRequest(BaseModel):
    query: str
    model: Optional[str] = MODEL_NAME

class TextToSqlResponse(BaseModel):
    sql: str
    query: str
    model: str

def read_schema() -> str:
    """Read the MySQL schema from file"""
    try:
        with open(SCHEMA_FILE, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "Schema file not found"

def extract_sql_from_response(response: str) -> str:
    """Extract SQL query from LLM response"""
    # Remove markdown code blocks if present
    response = re.sub(r'```sql\n?', '', response)
    response = re.sub(r'```\n?', '', response)
    
    # Try to extract SQL keywords pattern
    sql_pattern = r'(?:SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)[^;]*;?'
    matches = re.findall(sql_pattern, response, re.IGNORECASE)
    
    if matches:
        # Return the first SQL query found
        sql = matches[0].strip()
        if not sql.endswith(';'):
            sql += ';'
        return sql
    
    # If no SQL pattern found, clean up the response
    lines = response.strip().split('\n')
    # Remove explanation lines and keep only SQL
    sql_lines = []
    for line in lines:
        line = line.strip()
        if line and not any(word in line.lower() for word in ['explanation', 'note:', 'answer:', 'here', 'this', 'the query']):
            sql_lines.append(line)
    
    result = ' '.join(sql_lines).strip()
    if not result.endswith(';'):
        result += ';'
    return result

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}

@app.post("/text-to-sql")
async def text_to_sql(request: TextToSqlRequest) -> TextToSqlResponse:
    """Convert natural language query to SQL using the database schema"""
    try:
        schema = read_schema()

        prompt = f"""{SQL_SYSTEM_PROMPT}

DATABASE SCHEMA:
{schema}

USER REQUEST: {request.query}

IMPORTANT INSTRUCTIONS:
1. Return ONLY the SQL query, nothing else
2. Do not include explanations, notes, or markdown
3. The query must be valid MySQL syntax
4. End the query with a semicolon
5. Use table and column names exactly as they appear in the schema
6. If the request is ambiguous, make reasonable assumptions based on the schema

SQL Query:"""
        
        # Call Ollama API
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{OLLAMA_API_URL}/api/chat",
                json={
                    "model": request.model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False,
                    "temperature": 0.3,  # Lower temperature for more consistent SQL
                    "top_p": 0.9,
                }
            )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ollama error: {response.text}"
            )
        
        result = response.json()
        raw_response = result.get("message", {}).get("content", "")
        sql_query = extract_sql_from_response(raw_response)
        
        return TextToSqlResponse(
            sql=sql_query,
            query=request.query,
            model=request.model
        )
    
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Ollama at {OLLAMA_API_URL}. Make sure it's running."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat endpoint that connects to Ollama"""
    try:
        # Format messages for Ollama
        messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]
        
        # Call Ollama API
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{OLLAMA_API_URL}/api/chat",
                json={
                    "model": request.model,
                    "messages": messages,
                    "stream": False,
                    "temperature": request.temperature,
                    "top_p": request.top_p,
                }
            )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ollama error: {response.text}"
            )
        
        result = response.json()
        return ChatResponse(
            response=result.get("message", {}).get("content", ""),
            model=request.model
        )
    
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Ollama at {OLLAMA_API_URL}. Make sure it's running."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stream-chat")
async def stream_chat(request: ChatRequest):
    """Streaming chat endpoint"""
    try:
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]
        
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{OLLAMA_API_URL}/api/chat",
                json={
                    "model": request.model,
                    "messages": messages,
                    "stream": True,
                    "temperature": request.temperature,
                    "top_p": request.top_p,
                }
            )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ollama error: {response.text}"
            )
        
        async def event_generator():
            async for line in response.aiter_lines():
                if line:
                    import json
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
        
        return event_generator()
    
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Ollama at {OLLAMA_API_URL}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
