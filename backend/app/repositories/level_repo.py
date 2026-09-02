from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.level import Level


class LevelRepo:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_name(self, name: str) -> Level | None:
        # case-insensitive match, stored case returned; None when absent.
        # Search filter semantics (Task 5): None -> WHERE false, never a create.
        return self.db.execute(
            select(Level).where(func.lower(Level.name) == name.strip().lower())
        ).scalar_one_or_none()

    def get_or_create_by_name(self, name: str) -> Level:
        # Write path (Task 5). Reuse by case-insensitive match with STORED case;
        # create lowercased when absent. One query, then insert.
        existing = self.get_by_name(name)
        if existing is not None:
            return existing
        entity = Level(name=name.strip().lower())
        self.db.add(entity)
        self.db.commit()  # commit-stays-in-repo (legacy convention)
        self.db.refresh(entity)
        return entity

    def list_all(self) -> list[Level]:
        return list(self.db.scalars(select(Level).order_by(Level.name)).all())
