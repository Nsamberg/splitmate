from collections import defaultdict

from sqlmodel import Session, select

from .models import Expense, ExpenseParticipant, Member, Settlement


def compute_balances(db: Session) -> dict[int, int]:
    """Net balance per member, in cents. Positive = the group owes them."""
    balances: dict[int, int] = defaultdict(int)

    members = db.exec(select(Member)).all()
    for m in members:
        balances[m.id] = 0

    expenses = db.exec(select(Expense).where(Expense.deleted_at.is_(None))).all()
    for expense in expenses:
        balances[expense.paid_by_id] += expense.amount_cents
        shares = db.exec(
            select(ExpenseParticipant).where(ExpenseParticipant.expense_id == expense.id)
        ).all()
        for share in shares:
            balances[share.member_id] -= share.share_cents

    settlements = db.exec(select(Settlement).where(Settlement.deleted_at.is_(None))).all()
    for s in settlements:
        # from_member paid to_member: this discharges what from_member owed
        # (their balance moves toward/above zero) and reduces what the group
        # still owes to_member (their balance moves toward/below zero).
        balances[s.from_member_id] += s.amount_cents
        balances[s.to_member_id] -= s.amount_cents

    return dict(balances)


def suggest_settlements(balances: dict[int, int]) -> list[tuple[int, int, int]]:
    """Minimal set of (from_member_id, to_member_id, cents) transfers that would
    zero everyone out, via a greedy largest-debtor-pays-largest-creditor match."""
    debtors = [[member_id, -amount] for member_id, amount in balances.items() if amount < 0]
    creditors = [[member_id, amount] for member_id, amount in balances.items() if amount > 0]
    debtors.sort(key=lambda x: -x[1])
    creditors.sort(key=lambda x: -x[1])

    suggestions: list[tuple[int, int, int]] = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor_id, owed = debtors[i]
        creditor_id, due = creditors[j]
        pay = min(owed, due)
        if pay > 0:
            suggestions.append((debtor_id, creditor_id, pay))
        debtors[i][1] -= pay
        creditors[j][1] -= pay
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return suggestions
