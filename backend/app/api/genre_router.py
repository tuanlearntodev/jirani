from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import RoleChecker
from app.models import Account, RoleEnum
from app.schemas.genre_schema import GenreRead
from app.services.genre_service import GenreService

router = APIRouter(prefix="/genres", tags=["genres"])


@router.get("/", response_model=list[GenreRead])
def list_genres(
    user: Account = Depends(
        RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student])
    ),
    db: Session = Depends(get_db),
) -> list[GenreRead]:
    return GenreService(db).list_genres()
