from sqlmodel import Session, select

from . import config
from .models import AppSetting, Member


def seed_members(db: Session) -> None:
    if db.exec(select(Member)).first():
        return
    for name in config.SEED_MEMBERS:
        db.add(Member(name=name, is_admin=(name == config.ADMIN_MEMBER_NAME)))
    db.commit()


def seed_access_code(db: Session) -> None:
    if db.get(AppSetting, "access_code"):
        return
    db.add(AppSetting(key="access_code", value=config.INITIAL_ACCESS_CODE))
    db.commit()


def run_seed(db: Session) -> None:
    seed_members(db)
    seed_access_code(db)
