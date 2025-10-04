
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = "sqlite:///./saas.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()



def init_db():
    from . import models
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
