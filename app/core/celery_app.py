from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("rideseat")
celery_app.conf.broker_url = settings.celery_broker_url
celery_app.conf.result_backend = settings.celery_result_backend
celery_app.conf.task_routes = {"app.tasks.payment_tasks.*": {"queue": "payments"}}
celery_app.conf.beat_schedule = {
    "process-pending-intents": {
        "task": "app.tasks.payment_tasks.process_pending_intents",
        "schedule": 60.0,
    }
}
