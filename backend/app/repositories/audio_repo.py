from sqlalchemy.orm import Session
from app.models.audio import Audio
from app.schemas.audio_schema import Audio_Create
from datetime import datetime, timezone

class Audio_Repo:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def create_audio(self, audio_create: Audio_Create) -> Audio:
        new_audio = Audio(**audio_create.model_dump())
        self.db_session.add(new_audio)
        self.db_session.commit()
        self.db_session.refresh(new_audio)
        return new_audio

    def delete_audio(self, audio_id: int) -> Audio:
        audio = self.db_session.query(Audio).filter(Audio.id == audio_id).first()
        audio.deleted_at = datetime.now(timezone.utc)
        self.db_session.commit()
        self.db_session.refresh(audio)
        return audio

    def update_audio(self, audio_id: int, title: str, description: str) -> Audio:
        audio = self.db_session.query(Audio).filter(Audio.id == audio_id).first()
        if title:
            audio.title = title
        if description is not None:
            audio.description = description
        self.db_session.commit()
        self.db_session.refresh(audio)
        return audio