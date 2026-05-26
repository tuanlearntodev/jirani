from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Show all tables
    result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    tables = [r[0] for r in result]
    print("Tables:", tables)

    # Create video_tags if missing
    if "video_tags" not in tables:
        conn.execute(text("""
            CREATE TABLE video_tags (
                id INTEGER PRIMARY KEY,
                video_id INTEGER REFERENCES video(id) ON DELETE CASCADE,
                tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
                UNIQUE(video_id, tag_id)
            )
        """))
        print("video_tags created")
    else:
        print("video_tags already exists")

    # Create audio_tags if missing
    if "audio_tags" not in tables:
        conn.execute(text("""
            CREATE TABLE audio_tags (
                id INTEGER PRIMARY KEY,
                audio_id INTEGER REFERENCES audio(id) ON DELETE CASCADE,
                tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
                UNIQUE(audio_id, tag_id)
            )
        """))
        print("audio_tags created")
    else:
        print("audio_tags already exists")

    conn.commit()
    print("Done")