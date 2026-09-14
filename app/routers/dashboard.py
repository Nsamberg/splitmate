from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from ..db import get_session
from ..models import Expense, Member, Settlement
from ..money import format_cents
from ..security import require_member
from ..templating import render

router = APIRouter()


def _recent_activity(db: Session, limit: int = 20) -> list[dict]:
    members = {m.id: m for m in db.exec(select(Member)).all()}

    expenses = db.exec(
        select(Expense)
        .where(Expense.deleted_at.is_(None))
        .order_by(Expense.created_at.desc())
        .limit(limit)
    ).all()
    settlements = db.exec(
        select(Settlement)
        .where(Settlement.deleted_at.is_(None))
        .order_by(Settlement.created_at.desc())
        .limit(limit)
    ).all()

    activity = []
    for e in expenses:
        activity.append(
            {
                "type": "expense",
                "id": e.id,
                "when": e.created_at,
                "date": e.expense_date,
                "description": e.description,
                "amount": format_cents(e.amount_cents),
                "paid_by": members[e.paid_by_id].name,
                "created_by_id": e.created_by_id,
            }
        )
    for s in settlements:
        activity.append(
            {
                "type": "settlement",
                "id": s.id,
                "when": s.created_at,
                "date": s.settlement_date,
                "description": s.note or "Settlement",
                "amount": format_cents(s.amount_cents),
                "from_name": members[s.from_member_id].name,
                "to_name": members[s.to_member_id].name,
                "created_by_id": s.created_by_id,
            }
        )
    activity.sort(key=lambda a: a["when"], reverse=True)
    return activity[:limit]


@router.get("/")
def dashboard(
    request: Request,
    member: Member = Depends(require_member),
    db: Session = Depends(get_session),
):
    members = db.exec(select(Member).where(Member.active.is_(True)).order_by(Member.name)).all()
    activity = _recent_activity(db)
    return render(
        request,
        "dashboard.html",
        {
            "members": members,
            "activity": activity,
            "today": date.today().isoformat(),
        },
        member=member,
    )
