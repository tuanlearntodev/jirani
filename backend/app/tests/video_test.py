import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

test_url = "sqlite:///./video_test.db"

engine = create_engine(test_url, connect_args={"check_same_thread": False})
# check same thread allows multiple threads to use SQLite connection
# safe for testing 

test_local = sessionmaker(autocommit=False, autoflush = False, bind=engine)
