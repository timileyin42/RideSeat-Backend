# Import all models here so SQLAlchemy's mapper can resolve every relationship
# regardless of which entry point (API, Celery worker, Alembic) loads first.
from app.models.user import User
from app.models.trip import Trip
from app.models.booking import Booking
from app.models.payment import Payment
from app.models.message import Message
from app.models.notification import Notification
from app.models.device import Device
from app.models.review import Review
from app.models.ticket import Ticket
from app.models.vehicle import Vehicle

__all__ = [
    "User", "Trip", "Booking", "Payment", "Message",
    "Notification", "Device", "Review", "Ticket", "Vehicle",
]
