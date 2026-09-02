from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import RoleChecker
from app.models import Account, RoleEnum
from app.schemas.level_schema import LevelRead
from app.services.level_service import LevelService

router = APIRouter(prefix="/levels", tags=["levels"])


@router.get("/", response_model=list[LevelRead])
def list_levels(
    user: Account = Depends(
        RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student])
    ),
    db: Session = Depends(get_db),
) -> list[LevelRead]:
    return LevelService(db).list_levels()
