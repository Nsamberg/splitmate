from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from ..balances import (
    compute_balances,
    member_ledger,
    suggest_settlements,
    suggest_settlements_with_preferences,
)
from ..db import get_session
from ..models import Member
from ..money import format_cents
from ..security import require_member
from ..templating import render

router = APIRouter()


def _format_ledger(entries: list[dict]) -> list[dict]:
    formatted = []
    for entry in entries:
        cents = entry["cents"]
        sign = "+" if cents >= 0 else "-"
        formatted.append(
            {
                "date": entry["date"],
                "description": entry["description"],
                "amount": f"{sign}${format_cents(abs(cents))}",
                "positive": cents >= 0,
            }
        )
    return formatted


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

    ledger_cache: dict[int, list[dict]] = {}

    def get_ledger(member_id: int) -> list[dict]:
        if member_id not in ledger_cache:
            ledger_cache[member_id] = _format_ledger(member_ledger(db, member_id))
        return ledger_cache[member_id]

    def build_suggestion(debtor_id: int, creditor_id: int, cents: int, reason: str | None = None) -> dict:
        return {
            "from_id": debtor_id,
            "to_id": creditor_id,
            "from_name": members[debtor_id].name,
            "to_name": members[creditor_id].name,
            "amount": format_cents(cents),
            "amount_raw": f"{cents / 100:.2f}",
            "from_balance": format_cents(abs(balances[debtor_id])),
            "to_balance": format_cents(abs(balances[creditor_id])),
            "from_ledger": get_ledger(debtor_id),
            "to_ledger": get_ledger(creditor_id),
            "reason": reason,
        }

    suggestions = [
        build_suggestion(debtor_id, creditor_id, cents)
        for debtor_id, creditor_id, cents in suggest_settlements(balances)
    ]

    preferred_suggestions = [
        build_suggestion(s["from_id"], s["to_id"], s["cents"], reason=s["reason"])
        for s in suggest_settlements_with_preferences(db, balances)
    ]

    return render(
        request,
        "recap.html",
        {"rows": rows, "suggestions": suggestions, "preferred_suggestions": preferred_suggestions},
        member=member,
    )
