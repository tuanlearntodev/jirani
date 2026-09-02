from sqlalchemy.orm import Session

from app.repositories.genre_repo import GenreRepo
from app.schemas.genre_schema import GenreRead


class GenreService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_genres(self) -> list[GenreRead]:
        return [
            GenreRead.model_validate(entity) for entity in GenreRepo(self.db).list_all()
        ]
