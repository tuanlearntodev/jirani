from sqlalchemy.orm import Session
from app.models.video import Video
from app.schemas.video_schema import Video_Create
from datetime import datetime, timezone

class Video_Repo:
    def __init__(self, db_session:Session ): # constructor
        self.db_session = db_session

    def create_video(self, video_create: Video_Create) -> Video: # takes in pydantic schema and returns model which is sql alchemy
        new_video = Video(
            **video_create.model_dump())
        self.db_session.add(new_video)
        self.db_session.commit()
        self.db_session.refresh(new_video)
        return new_video
    
    def delete_video(self, video_id: int) -> Video: 
        video = self.db_session.query(Video).filter(Video.id == video_id).first()
        video.deleted_at = datetime.now(timezone.utc)
        self.db_session.commit()
        self.db_session.refresh(video)
        return video

    