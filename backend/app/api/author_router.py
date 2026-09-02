from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import RoleChecker
from app.models import Account, RoleEnum
from app.schemas.author_schema import AuthorRead
from app.services.author_service import AuthorService

router = APIRouter(prefix="/authors", tags=["authors"])


@router.get("/", response_model=list[AuthorRead])
def list_authors(
    user: Account = Depends(
        RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student])
    ),
    db: Session = Depends(get_db),
) -> list[AuthorRead]:
    return AuthorService(db).list_authors()
