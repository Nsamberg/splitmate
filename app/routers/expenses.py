from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from ..db import get_session
from ..models import Expense, ExpenseParticipant, Member, utcnow
from ..money import format_cents, parse_amount_to_cents, split_equally
from ..security import flash, require_member
from ..templating import render

router = APIRouter()


def _can_modify(member: Member, created_by_id: int) -> bool:
    return member.is_admin or member.id == created_by_id


@router.post("/expenses")
def create_expense(
    request: Request,
    description: str = Form(...),
    amount: str = Form(...),
    paid_by_id: int = Form(...),
    expense_date: date = Form(...),
    participant_ids: list[int] = Form(...),
    member: Member = Depends(require_member),
    db: Session = Depends(get_session),
):
    try:
        cents = parse_amount_to_cents(amount)
    except ValueError:
        flash(request, "Please enter a valid amount greater than zero.", "error")
        return RedirectResponse("/", status_code=303)

    if not participant_ids:
        flash(request, "Pick at least one person to split this with.", "error")
        return RedirectResponse("/", status_code=303)

    payer = db.get(Member, paid_by_id)
    if not payer or not payer.active:
        flash(request, "Invalid payer.", "error")
        return RedirectResponse("/", status_code=303)

    expense = Expense(
        description=description.strip() or "Expense",
        amount_cents=cents,
        paid_by_id=paid_by_id,
        expense_date=expense_date,
        created_by_id=member.id,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)

    shares = split_equally(cents, len(participant_ids))
    for participant_id, share_cents in zip(participant_ids, shares):
        db.add(
            ExpenseParticipant(
                expense_id=expense.id, member_id=participant_id, share_cents=share_cents
            )
        )
    db.commit()

    flash(request, "Expense added.", "success")
    return RedirectResponse("/", status_code=303)


@router.get("/expenses/{expense_id}/edit")
def edit_expense_form(
    expense_id: int,
    request: Request,
    member: Member = Depends(require_member),
    db: Session = Depends(get_session),
):
    expense = db.get(Expense, expense_id)
    if not expense or expense.deleted_at is not None:
        flash(request, "Expense not found.", "error")
        return RedirectResponse("/", status_code=303)
    if not _can_modify(member, expense.created_by_id):
        flash(request, "Only the person who added this expense (or an admin) can edit it.", "error")
        return RedirectResponse("/", status_code=303)

    participants = db.exec(
        select(ExpenseParticipant).where(ExpenseParticipant.expense_id == expense_id)
    ).all()
    members = db.exec(select(Member).where(Member.active.is_(True)).order_by(Member.name)).all()
    return render(
        request,
        "expense_edit.html",
        {
            "expense": expense,
            "participant_ids": {p.member_id for p in participants},
            "members": members,
            "amount": format_cents(expense.amount_cents),
        },
        member=member,
    )


@router.post("/expenses/{expense_id}/edit")
def edit_expense_submit(
    expense_id: int,
    request: Request,
    description: str = Form(...),
    amount: str = Form(...),
    paid_by_id: int = Form(...),
    expense_date: date = Form(...),
    participant_ids: list[int] = Form(...),
    member: Member = Depends(require_member),
    db: Session = Depends(get_session),
):
    expense = db.get(Expense, expense_id)
    if not expense or expense.deleted_at is not None:
        flash(request, "Expense not found.", "error")
        return RedirectResponse("/", status_code=303)
    if not _can_modify(member, expense.created_by_id):
        flash(request, "Only the person who added this expense (or an admin) can edit it.", "error")
        return RedirectResponse("/", status_code=303)

    try:
        cents = parse_amount_to_cents(amount)
    except ValueError:
        flash(request, "Please enter a valid amount greater than zero.", "error")
        return RedirectResponse(f"/expenses/{expense_id}/edit", status_code=303)
    if not participant_ids:
        flash(request, "Pick at least one person to split this with.", "error")
        return RedirectResponse(f"/expenses/{expense_id}/edit", status_code=303)

    expense.description = description.strip() or "Expense"
    expense.amount_cents = cents
    expense.paid_by_id = paid_by_id
    expense.expense_date = expense_date
    db.add(expense)

    old_participants = db.exec(
        select(ExpenseParticipant).where(ExpenseParticipant.expense_id == expense_id)
    ).all()
    for p in old_participants:
        db.delete(p)
    db.commit()

    shares = split_equally(cents, len(participant_ids))
    for participant_id, share_cents in zip(participant_ids, shares):
        db.add(
            ExpenseParticipant(
                expense_id=expense_id, member_id=participant_id, share_cents=share_cents
            )
        )
    db.commit()

    flash(request, "Expense updated.", "success")
    return RedirectResponse("/", status_code=303)


@router.post("/expenses/{expense_id}/delete")
def delete_expense(
    expense_id: int,
    request: Request,
    member: Member = Depends(require_member),
    db: Session = Depends(get_session),
):
    expense = db.get(Expense, expense_id)
    if not expense or expense.deleted_at is not None:
        flash(request, "Expense not found.", "error")
        return RedirectResponse("/", status_code=303)
    if not _can_modify(member, expense.created_by_id):
        flash(request, "Only the person who added this expense (or an admin) can delete it.", "error")
        return RedirectResponse("/", status_code=303)

    expense.deleted_at = utcnow()
    expense.deleted_by_id = member.id
    db.add(expense)
    db.commit()

    flash(request, "Expense deleted.", "success")
    return RedirectResponse("/", status_code=303)
