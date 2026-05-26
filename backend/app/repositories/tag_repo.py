from sqlalchemy.orm import Session, joinedload
from app.models import Book, Tag
from app.schemas.book_schema import TagCreate

class TagRepo:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_tag_by_id(self, tag_id: int) -> Tag:
        return self.db_session.query(Tag).options(joinedload(Tag.books)).filter(Tag.id == tag_id).first()

    def create_tag(self, tag_create: TagCreate) -> Tag:
        new_tag = Tag(**tag_create.model_dump())
        self.db_session.add(new_tag)
        self.db_session.commit()
        self.db_session.refresh(new_tag)
        return new_tag
    
    def get_all_tags(self) -> list[Tag]:
        return self.db_session.query(Tag).all()

