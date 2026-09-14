from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from ..db import get_session
from ..models import Member
from ..security import flash, get_access_code, require_access_code
from ..templating import render

router = APIRouter()


@router.get("/login")
def login_form(request: Request):
    if request.session.get("member_id"):
        return RedirectResponse("/", status_code=303)
    return render(request, "login_code.html")


@router.post("/login")
def login_submit(
    request: Request,
    access_code: str = Form(...),
    db: Session = Depends(get_session),
):
    if access_code.strip() and access_code.strip() == get_access_code(db):
        request.session["access_ok"] = True
        return RedirectResponse("/login/member", status_code=303)
    flash(request, "Incorrect access code.", "error")
    return RedirectResponse("/login", status_code=303)


@router.get("/login/member")
def choose_member_form(request: Request, db: Session = Depends(get_session)):
    require_access_code(request)
    members = db.exec(select(Member).where(Member.active.is_(True)).order_by(Member.name)).all()
    return render(request, "login_member.html", {"members": members})


@router.post("/login/member")
def choose_member_submit(
    request: Request,
    member_id: int = Form(...),
    db: Session = Depends(get_session),
):
    require_access_code(request)
    member = db.get(Member, member_id)
    if not member or not member.active:
        flash(request, "Please pick a valid member.", "error")
        return RedirectResponse("/login/member", status_code=303)
    request.session["member_id"] = member.id
    return RedirectResponse("/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
