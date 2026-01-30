from uuid import UUID

from celery import Task

from app.core.celery_app import celery_app
from app.repositories.booking_repo import BookingRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.services.payment_service import PaymentService


def _build_payment_service() -> PaymentService:
    return PaymentService(
        PaymentRepository(),
        BookingRepository(),
        TripRepository(),
        UserRepository(),
    )


@celery_app.task(
    name="app.tasks.payment_tasks.process_payment_intent",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_payment_intent(task: Task, payment_id: str) -> None:
    service = _build_payment_service()
    try:
        service.process_payment_intent(UUID(payment_id))
    except Exception as exc:
        raise task.retry(exc=exc)


@celery_app.task(
    name="app.tasks.payment_tasks.process_payout",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_payout(task: Task, booking_id: str) -> None:
    service = _build_payment_service()
    try:
        service.process_payout(booking_id)
    except Exception as exc:
        raise task.retry(exc=exc)


@celery_app.task(name="app.tasks.payment_tasks.process_pending_intents")
def process_pending_intents() -> None:
    service = _build_payment_service()
    service.process_pending_intents()


def enqueue_payment_intent(payment_id: UUID) -> None:
    process_payment_intent.delay(str(payment_id))


def enqueue_payout(booking_id: UUID) -> None:
    process_payout.delay(str(booking_id))
