from sqlmodel import Session, SQLModel, create_engine

from . import config

engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
