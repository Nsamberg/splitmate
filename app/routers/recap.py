from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from ..balances import compute_balances, suggest_settlements
from ..db import get_session
from ..models import Member
from ..money import format_cents
from ..security import require_member
from ..templating import render

router = APIRouter()


@router.get("/recap")
def recap(
    request: Request,
    member: Member = Depends(require_member),
    db: Session = Depends(get_session),
):
    members = {m.id: m for m in db.exec(select(Member)).all()}
    balances = compute_balances(db)

    rows = []
    for member_id, cents in balances.items():
        m = members.get(member_id)
        if not m or not m.active:
            continue
        rows.append(
            {
                "name": m.name,
                "cents": cents,
                "amount": format_cents(abs(cents)),
                "status": "is owed" if cents > 0 else ("owes the group" if cents < 0 else "is settled up"),
            }
        )
    rows.sort(key=lambda r: r["cents"])

    suggestions = []
    for debtor_id, creditor_id, cents in suggest_settlements(balances):
        suggestions.append(
            {
                "from_id": debtor_id,
                "to_id": creditor_id,
                "from_name": members[debtor_id].name,
                "to_name": members[creditor_id].name,
                "amount": format_cents(cents),
                "amount_raw": f"{cents / 100:.2f}",
            }
        )

    return render(
        request,
        "recap.html",
        {"rows": rows, "suggestions": suggestions},
        member=member,
    )
