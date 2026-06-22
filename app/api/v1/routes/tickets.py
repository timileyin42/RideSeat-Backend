"""Ticket routes — user-facing and admin."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.constants import TicketStatus
from app.core.dependencies import get_current_user, get_db, require_admin
from app.repositories.ticket_repo import TicketRepository
from app.schemas.base import DataResponse
from app.schemas.ticket import TicketAdminUpdate, TicketCreate, TicketResponse
from app.services.ticket_service import TicketService

router = APIRouter()
_svc = TicketService(TicketRepository())


# ── user endpoints ─────────────────────────────────────────────────────────────

@router.post("", response_model=TicketResponse, status_code=201)
def raise_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        ticket = _svc.raise_ticket(
            db,
            reporter=current_user,
            category=payload.category,
            subject=payload.subject,
            description=payload.description,
            reported_user_id=payload.reported_user_id,
            trip_id=payload.trip_id,
        )
        db.commit()
        return ticket
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/me", response_model=DataResponse[TicketResponse])
def my_tickets(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return DataResponse(data=_svc.my_tickets(db, current_user))


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return _svc.get_ticket(db, current_user, ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── admin endpoints ────────────────────────────────────────────────────────────

@router.get("/admin/all", response_model=DataResponse[TicketResponse])
def admin_list_tickets(
    status: TicketStatus | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    return DataResponse(data=_svc.list_tickets(db, current_user, status=status))


@router.patch("/admin/{ticket_id}", response_model=TicketResponse)
def admin_update_ticket(
    ticket_id: UUID,
    payload: TicketAdminUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    try:
        ticket = _svc.update_ticket(
            db,
            actor=current_user,
            ticket_id=ticket_id,
            status=payload.status,
            admin_note=payload.admin_note,
        )
        db.commit()
        return ticket
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
