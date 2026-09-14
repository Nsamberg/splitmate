from typing import Optional

from fastapi import Depends, Request
from sqlmodel import Session

from .db import get_session
from .models import AppSetting, Member


class RedirectException(Exception):
    """Raised by auth dependencies to bounce an unauthenticated/unauthorized
    request to another page. Handled centrally in main.py."""

    def __init__(self, url: str) -> None:
        self.url = url


def get_access_code(db: Session) -> str:
    setting = db.get(AppSetting, "access_code")
    return setting.value if setting else ""


def set_access_code(db: Session, new_code: str) -> None:
    setting = db.get(AppSetting, "access_code")
    if setting:
        setting.value = new_code
    else:
        db.add(AppSetting(key="access_code", value=new_code))
    db.commit()


def get_current_member(request: Request, db: Session = Depends(get_session)) -> Optional[Member]:
    member_id = request.session.get("member_id")
    if not member_id:
        return None
    member = db.get(Member, member_id)
    if member is None or not member.active:
        return None
    return member


def require_access_code(request: Request) -> None:
    if not request.session.get("access_ok"):
        raise RedirectException("/login")


def require_member(request: Request, db: Session = Depends(get_session)) -> Member:
    if not request.session.get("access_ok"):
        raise RedirectException("/login")
    member = get_current_member(request, db)
    if member is None:
        raise RedirectException("/login/member")
    return member


def require_admin(member: Member = Depends(require_member)) -> Member:
    if not member.is_admin:
        raise RedirectException("/")
    return member


def flash(request: Request, message: str, category: str = "info") -> None:
    flashes = request.session.get("_flashes", [])
    flashes.append({"message": message, "category": category})
    request.session["_flashes"] = flashes


def pop_flashes(request: Request) -> list[dict]:
    return request.session.pop("_flashes", [])
