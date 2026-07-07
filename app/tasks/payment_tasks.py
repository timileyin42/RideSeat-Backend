import logging
from uuid import UUID

from celery import Task

from app.core.celery_app import celery_app
from app.repositories.booking_repo import BookingRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)


def _build_payment_service() -> PaymentService:
    return PaymentService(
        PaymentRepository(),
        BookingRepository(),
        TripRepository(),
        UserRepository(),
    )


def _on_failure(task_name: str, task_id: str, args: list, exc: Exception) -> None:
    """Log exhausted tasks and route them to the DLQ for manual inspection."""
    logger.error(
        "Payment task exhausted retries — sending to DLQ",
        extra={"task": task_name, "task_id": task_id, "args": args, "error": str(exc)},
    )
    celery_app.send_task(
        "app.tasks.payment_tasks.dead_letter",
        args=[task_name, task_id, args, str(exc)],
        queue="payments.dlq",
    )


@celery_app.task(
    name="app.tasks.payment_tasks.process_payment_intent",
    bind=True,
    max_retries=5,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_payment_intent(task: Task, payment_id: str) -> None:
    service = _build_payment_service()
    try:
        service.process_payment_intent(UUID(payment_id))
    except Exception as exc:
        if task.request.retries >= task.max_retries:
            _on_failure(task.name, task.request.id, [payment_id], exc)
            return
        # Exponential backoff: 30s → 60s → 120s → 240s → 480s
        raise task.retry(exc=exc, countdown=30 * (2 ** task.request.retries))


@celery_app.task(
    name="app.tasks.payment_tasks.process_payout",
    bind=True,
    max_retries=5,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_payout(task: Task, booking_id: str) -> None:
    service = _build_payment_service()
    try:
        service.process_payout(booking_id)
    except Exception as exc:
        if task.request.retries >= task.max_retries:
            _on_failure(task.name, task.request.id, [booking_id], exc)
            return
        raise task.retry(exc=exc, countdown=30 * (2 ** task.request.retries))


@celery_app.task(name="app.tasks.payment_tasks.process_pending_intents")
def process_pending_intents() -> None:
    service = _build_payment_service()
    service.process_pending_intents()


@celery_app.task(name="app.tasks.payment_tasks.dead_letter", queue="payments.dlq")
def dead_letter(original_task: str, task_id: str, args: list, error: str) -> None:
    """Sink for exhausted payment tasks. Ops replay with: celery call <original_task> --args <args>"""
    logger.critical(
        "Dead-lettered payment task",
        extra={"original_task": original_task, "task_id": task_id, "args": args, "error": error},
    )


def enqueue_payment_intent(payment_id: UUID) -> None:
    process_payment_intent.delay(str(payment_id))


def enqueue_payout(booking_id: UUID) -> None:
    process_payout.delay(str(booking_id))
