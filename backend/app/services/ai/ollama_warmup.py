import httpx

from app.config import OLLAMA_BASE_URL, OLLAMA_KEEP_ALIVE, OLLAMA_NUM_GPU, OLLAMA_SQL_MODEL, OLLAMA_WARMUP_ON_STARTUP
from app.services.ai.ollama import post_ollama_chat_completion


async def warm_ollama_sql_model() -> None:
    """Pre-load the SQL model into GPU VRAM so the first user request is faster."""
    if not OLLAMA_WARMUP_ON_STARTUP:
        return
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await post_ollama_chat_completion(
                client,
                {
                    "model": OLLAMA_SQL_MODEL,
                    "stream": False,
                    "keep_alive": OLLAMA_KEEP_ALIVE,
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "Output one line only:\n"
                                "-- Reason: warmup\n"
                                "SELECT 1 AS ok;"
                            ),
                        }
                    ],
                    "options": {
                        "temperature": 0.0,
                        "num_ctx": 512,
                        "num_predict": 32,
                        "num_gpu": OLLAMA_NUM_GPU,
                    },
                },
            )
            if response.status_code == 200:
                print(f"[warm] Ollama model ready on GPU: {OLLAMA_SQL_MODEL}")
            else:
                print(f"[warm] Ollama warmup returned {response.status_code}")
    except Exception as exc:
        print(f"[warm] Ollama warmup skipped: {exc}")


async def ollama_runtime_info() -> dict:
    """Inspect Ollama /api/ps for processor (CPU vs GPU)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/ps")
            if response.status_code != 200:
                return {"reachable": True, "models": [], "error": response.text[:200]}
            payload = response.json()
            models = []
            for item in payload.get("models") or []:
                models.append(
                    {
                        "name": item.get("name"),
                        "size": item.get("size"),
                        "processor": item.get("processor") or item.get("details", {}).get("processor"),
                    }
                )
            return {"reachable": True, "models": models}
    except Exception as exc:
        return {"reachable": False, "models": [], "error": str(exc)}
