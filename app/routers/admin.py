import secrets
import string

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from ..db import get_session
from ..models import Member
from ..security import flash, get_access_code, require_admin, set_access_code
from ..templating import render

router = APIRouter(prefix="/admin")

CODE_ALPHABET = string.ascii_uppercase + string.digits


@router.get("")
def admin_home(
    request: Request,
    member: Member = Depends(require_admin),
    db: Session = Depends(get_session),
):
    members = db.exec(select(Member).order_by(Member.name)).all()
    return render(
        request,
        "admin.html",
        {"members": members, "access_code": get_access_code(db)},
        member=member,
    )


@router.post("/members")
def add_member(
    request: Request,
    name: str = Form(...),
    member: Member = Depends(require_admin),
    db: Session = Depends(get_session),
):
    name = name.strip()
    if not name:
        flash(request, "Name can't be empty.", "error")
        return RedirectResponse("/admin", status_code=303)
    existing = db.exec(select(Member).where(Member.name == name)).first()
    if existing:
        flash(request, f"{name} already exists.", "error")
        return RedirectResponse("/admin", status_code=303)
    db.add(Member(name=name))
    db.commit()
    flash(request, f"Added {name}.", "success")
    return RedirectResponse("/admin", status_code=303)


@router.post("/members/{member_id}/rename")
def rename_member(
    member_id: int,
    request: Request,
    name: str = Form(...),
    member: Member = Depends(require_admin),
    db: Session = Depends(get_session),
):
    target = db.get(Member, member_id)
    name = name.strip()
    if not target or not name:
        flash(request, "Invalid member or name.", "error")
        return RedirectResponse("/admin", status_code=303)
    target.name = name
    db.add(target)
    db.commit()
    flash(request, "Member renamed.", "success")
    return RedirectResponse("/admin", status_code=303)


@router.post("/members/{member_id}/toggle-active")
def toggle_member_active(
    member_id: int,
    request: Request,
    member: Member = Depends(require_admin),
    db: Session = Depends(get_session),
):
    target = db.get(Member, member_id)
    if not target:
        flash(request, "Member not found.", "error")
        return RedirectResponse("/admin", status_code=303)
    if target.id == member.id and target.active:
        flash(request, "You can't deactivate yourself.", "error")
        return RedirectResponse("/admin", status_code=303)
    target.active = not target.active
    db.add(target)
    db.commit()
    flash(request, f"{target.name} {'reactivated' if target.active else 'deactivated'}.", "success")
    return RedirectResponse("/admin", status_code=303)


@router.post("/members/{member_id}/preference")
def set_member_preference(
    member_id: int,
    request: Request,
    preferred_creditor_id: str = Form(""),
    preference_note: str = Form(""),
    member: Member = Depends(require_admin),
    db: Session = Depends(get_session),
):
    target = db.get(Member, member_id)
    if not target:
        flash(request, "Member not found.", "error")
        return RedirectResponse("/admin", status_code=303)

    preferred_id = int(preferred_creditor_id) if preferred_creditor_id else None
    if preferred_id == member_id:
        flash(request, "A member can't prefer paying themselves.", "error")
        return RedirectResponse("/admin", status_code=303)
    if preferred_id is not None and not db.get(Member, preferred_id):
        flash(request, "Invalid preferred recipient.", "error")
        return RedirectResponse("/admin", status_code=303)

    target.preferred_creditor_id = preferred_id
    target.preference_note = preference_note.strip() or None
    db.add(target)
    db.commit()
    flash(request, f"Updated {target.name}'s payment preference.", "success")
    return RedirectResponse("/admin", status_code=303)


@router.post("/access-code/regenerate")
def regenerate_access_code(
    request: Request,
    member: Member = Depends(require_admin),
    db: Session = Depends(get_session),
):
    new_code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
    set_access_code(db, new_code)
    flash(
        request,
        f"New access code: {new_code}. Share it with the group now — it won't be shown again after you leave this page.",
        "success",
    )
    return RedirectResponse("/admin", status_code=303)


@router.post("/access-code/set")
def set_access_code_manually(
    request: Request,
    new_code: str = Form(...),
    member: Member = Depends(require_admin),
    db: Session = Depends(get_session),
):
    new_code = new_code.strip()
    if not new_code:
        flash(request, "Access code can't be empty.", "error")
        return RedirectResponse("/admin", status_code=303)
    set_access_code(db, new_code)
    flash(request, "Access code updated.", "success")
    return RedirectResponse("/admin", status_code=303)
