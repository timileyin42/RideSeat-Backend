"""Ticket service."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.constants import TicketCategory, TicketStatus
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.ticket_repo import TicketRepository


class TicketService:
    def __init__(self, repo: TicketRepository) -> None:
        self.repo = repo

    def raise_ticket(
        self,
        db: Session,
        reporter: User,
        category: TicketCategory,
        subject: str,
        description: str,
        reported_user_id: UUID | None = None,
        trip_id: UUID | None = None,
    ) -> Ticket:
        ticket = Ticket(
            reporter_id=reporter.id,
            reported_user_id=reported_user_id,
            trip_id=trip_id,
            category=category,
            subject=subject,
            description=description,
            status=TicketStatus.OPEN,
        )
        return self.repo.create(db, ticket)

    def get_ticket(self, db: Session, actor: User, ticket_id: UUID) -> Ticket:
        ticket = self.repo.get_by_id(db, ticket_id)
        if not ticket:
            raise ValueError("Ticket not found")
        if not actor.is_admin and ticket.reporter_id != actor.id:
            raise ValueError("Not authorised")
        return ticket

    def my_tickets(self, db: Session, reporter: User) -> list[Ticket]:
        return self.repo.list_by_reporter(db, reporter.id)

    # ── admin ──────────────────────────────────────────────────────────────────

    def list_tickets(self, db: Session, actor: User, status: TicketStatus | None = None) -> list[Ticket]:
        if not actor.is_admin:
            raise ValueError("Admin only")
        return self.repo.list_all(db, status=status)

    def update_ticket(
        self,
        db: Session,
        actor: User,
        ticket_id: UUID,
        status: TicketStatus | None = None,
        admin_note: str | None = None,
    ) -> Ticket:
        if not actor.is_admin:
            raise ValueError("Admin only")
        ticket = self.repo.get_by_id(db, ticket_id)
        if not ticket:
            raise ValueError("Ticket not found")
        if status:
            ticket.status = status
            if status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
                ticket.resolved_by = actor.id
        if admin_note is not None:
            ticket.admin_note = admin_note
        ticket.updated_at = datetime.now(timezone.utc)
        return self.repo.update(db, ticket)
