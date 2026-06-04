from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import TextToSqlRequest, TextToSqlResponse
from app.database.models import UserModel
from app.database.session import get_db
from app.dependencies import get_current_user
from app.services.sql.generation import generate_sql

router = APIRouter(tags=["sql"])


@router.post("/text-to-sql", response_model=TextToSqlResponse)
async def text_to_sql(
    request: TextToSqlRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await generate_sql(request, current_user, db)
