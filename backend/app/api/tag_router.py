from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.repositories.tag_repo import TagRepo
from app.schemas.tag_schema import TagRead
from typing import List

router = APIRouter(prefix="/tags", tags=["tags"])

@router.get("/", response_model=List[TagRead])
def get_all_tags(db: Session = Depends(get_db)):
    return TagRepo(db).get_all_tags()