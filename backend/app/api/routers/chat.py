from fastapi import APIRouter, Depends

from app.api.schemas import ChatRequest, ChatResponse
from app.database.models import UserModel
from app.dependencies import get_current_user
from app.services.chat import chat_completion, chat_stream_response

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    _current_user: UserModel = Depends(get_current_user),
) -> ChatResponse:
    return await chat_completion(request)


@router.post("/chat-stream")
async def chat_stream(
    request: ChatRequest,
    _current_user: UserModel = Depends(get_current_user),
):
    return await chat_stream_response(request)
