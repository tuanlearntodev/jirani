from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.genre import Genre


class GenreRepo:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_name(self, name: str) -> Genre | None:
        # case-insensitive match, stored case returned; None when absent.
        # Search filter semantics (Task 5): None -> WHERE false, never a create.
        return self.db.execute(
            select(Genre).where(func.lower(Genre.name) == name.strip().lower())
        ).scalar_one_or_none()

    def get_or_create_by_name(self, name: str) -> Genre:
        # Write path (Task 5). Reuse by case-insensitive match with STORED case;
        # create lowercased when absent. One query, then insert.
        existing = self.get_by_name(name)
        if existing is not None:
            return existing
        entity = Genre(name=name.strip().lower())
        self.db.add(entity)
        self.db.commit()  # commit-stays-in-repo (legacy convention)
        self.db.refresh(entity)
        return entity

    def list_all(self) -> list[Genre]:
        return list(self.db.scalars(select(Genre).order_by(Genre.name)).all())
