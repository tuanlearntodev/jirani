from sqlalchemy.orm import Session

from app.repositories.level_repo import LevelRepo
from app.schemas.level_schema import LevelRead


class LevelService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_levels(self) -> list[LevelRead]:
        return [
            LevelRead.model_validate(entity) for entity in LevelRepo(self.db).list_all()
        ]
