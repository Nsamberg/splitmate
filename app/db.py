from sqlmodel import Session, SQLModel, create_engine

from . import config

engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})

# Lightweight, no-framework migrations for columns added after a table
# already existed on someone's deployed DB. create_all() only creates
# missing *tables* — it never alters an existing one — so any new column
# added to a model needs an entry here too, or existing deployments will
# hit "no such column" once the new code runs. Safe to run every startup:
# each step checks first and no-ops if already applied.
_MIGRATIONS = [
    ("member", "preferred_creditor_id", "INTEGER REFERENCES member(id)"),
    ("member", "preference_note", "VARCHAR"),
]


def _run_migrations() -> None:
    with engine.begin() as conn:
        for table, column, ddl_type in _MIGRATIONS:
            existing_columns = {
                row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            }
            if column not in existing_columns:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _run_migrations()


def get_session():
    with Session(engine) as session:
        yield session
