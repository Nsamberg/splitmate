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


def seed_payment_preferences(db: Session) -> None:
    """Fill in each member's initial payment-routing preference if they
    don't have one yet. Runs on every startup (not just first run) so it
    also backfills members created before this feature existed — but never
    overwrites a preference that's already set, whether seeded earlier or
    edited later via /admin."""
    members_by_name = {m.name: m for m in db.exec(select(Member)).all()}
    changed = False
    for name, (preferred_name, note) in config.PAYMENT_PREFERENCES.items():
        member = members_by_name.get(name)
        if not member or member.preferred_creditor_id is not None or member.preference_note:
            continue
        if preferred_name:
            preferred = members_by_name.get(preferred_name)
            if preferred:
                member.preferred_creditor_id = preferred.id
        member.preference_note = note
        db.add(member)
        changed = True
    if changed:
        db.commit()


def run_seed(db: Session) -> None:
    seed_members(db)
    seed_access_code(db)
    seed_payment_preferences(db)
