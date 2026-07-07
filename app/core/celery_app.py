from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("rideseat")
celery_app.conf.broker_url = settings.celery_broker_url
celery_app.conf.result_backend = settings.celery_result_backend
celery_app.conf.task_routes = {"app.tasks.payment_tasks.*": {"queue": "payments"}}

# Reliability: don't ack until the task succeeds; re-queue if worker dies mid-task
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True

# Prevent runaway retries from flooding the broker
celery_app.conf.task_max_retries = 5

# Dead-letter queue: exhausted tasks land here for inspection instead of being dropped
celery_app.conf.task_queues = {
    "payments": {"exchange": "payments", "routing_key": "payments"},
    "payments.dlq": {"exchange": "payments.dlq", "routing_key": "payments.dlq"},
}
celery_app.conf.task_default_queue = "default"

celery_app.conf.beat_schedule = {
    "process-pending-intents": {
        "task": "app.tasks.payment_tasks.process_pending_intents",
        "schedule": 60.0,
    }
}
