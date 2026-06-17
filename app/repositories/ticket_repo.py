"""Ticket repository."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.constants import TicketStatus
from app.models.ticket import Ticket


class TicketRepository:
    def create(self, db: Session, ticket: Ticket) -> Ticket:
        db.add(ticket)
        db.flush()
        return ticket

    def get_by_id(self, db: Session, ticket_id: UUID) -> Ticket | None:
        return db.get(Ticket, ticket_id)

    def list_by_reporter(self, db: Session, reporter_id: UUID, limit: int = 50) -> list[Ticket]:
        return (
            db.query(Ticket)
            .filter(Ticket.reporter_id == reporter_id)
            .order_by(Ticket.created_at.desc())
            .limit(limit)
            .all()
        )

    def list_all(self, db: Session, status: TicketStatus | None = None, limit: int = 100) -> list[Ticket]:
        q = db.query(Ticket).order_by(Ticket.created_at.desc())
        if status:
            q = q.filter(Ticket.status == status)
        return q.limit(limit).all()

    def update(self, db: Session, ticket: Ticket) -> Ticket:
        db.flush()
        return ticket
