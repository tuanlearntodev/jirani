from sqlalchemy.orm import Session

from app.repositories.author_repo import AuthorRepo
from app.schemas.author_schema import AuthorRead


class AuthorService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_authors(self) -> list[AuthorRead]:
        return [
            AuthorRead.model_validate(entity)
            for entity in AuthorRepo(self.db).list_all()
        ]
