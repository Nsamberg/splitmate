from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from ..db import get_session
from ..models import Member, Settlement
from ..money import parse_amount_to_cents
from ..security import flash, require_member
from ..templating import render

router = APIRouter()


def _can_modify(member: Member, created_by_id: int) -> bool:
    return member.is_admin or member.id == created_by_id


@router.get("/settle")
def settle_form(
    request: Request,
    member: Member = Depends(require_member),
    db: Session = Depends(get_session),
    from_member_id: Optional[int] = None,
    to_member_id: Optional[int] = None,
    amount: Optional[str] = None,
):
    members = db.exec(select(Member).where(Member.active.is_(True)).order_by(Member.name)).all()
    return render(
        request,
        "settle.html",
        {
            "members": members,
            "today": date.today().isoformat(),
            "prefill": {
                # Default "From" to whoever's logged in, unless a specific
                # transfer was prefilled from the recap page's suggestions.
                "from_member_id": from_member_id if from_member_id is not None else member.id,
                "to_member_id": to_member_id,
                "amount": amount,
            },
        },
        member=member,
    )


@router.post("/settle")
def settle_submit(
    request: Request,
    from_member_id: int = Form(...),
    to_member_id: int = Form(...),
    amount: str = Form(...),
    settlement_date: date = Form(...),
    note: str = Form(""),
    member: Member = Depends(require_member),
    db: Session = Depends(get_session),
):
    if from_member_id == to_member_id:
        flash(request, "Pick two different people.", "error")
        return RedirectResponse("/settle", status_code=303)
    try:
        cents = parse_amount_to_cents(amount)
    except ValueError:
        flash(request, "Please enter a valid amount greater than zero.", "error")
        return RedirectResponse("/settle", status_code=303)

    from_member = db.get(Member, from_member_id)
    to_member = db.get(Member, to_member_id)
    if not from_member or not to_member:
        flash(request, "Invalid members selected.", "error")
        return RedirectResponse("/settle", status_code=303)

    settlement = Settlement(
        from_member_id=from_member_id,
        to_member_id=to_member_id,
        amount_cents=cents,
        settlement_date=settlement_date,
        note=note.strip() or None,
        created_by_id=member.id,
    )
    db.add(settlement)
    db.commit()

    flash(request, "Transfer recorded.", "success")
    return RedirectResponse("/recap", status_code=303)


@router.post("/settlements/{settlement_id}/delete")
def delete_settlement(
    settlement_id: int,
    request: Request,
    member: Member = Depends(require_member),
    db: Session = Depends(get_session),
):
    settlement = db.get(Settlement, settlement_id)
    if not settlement or settlement.deleted_at is not None:
        flash(request, "Transfer not found.", "error")
        return RedirectResponse("/recap", status_code=303)
    if not _can_modify(member, settlement.created_by_id):
        flash(request, "Only the person who recorded this transfer (or an admin) can delete it.", "error")
        return RedirectResponse("/recap", status_code=303)

    settlement.deleted_at = datetime.utcnow()
    settlement.deleted_by_id = member.id
    db.add(settlement)
    db.commit()

    flash(request, "Transfer deleted.", "success")
    return RedirectResponse("/recap", status_code=303)
