"""Review service."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.constants import BookingStatus, NotificationType
from app.models.review import Review
from app.models.user import User
from app.repositories.booking_repo import BookingRepository
from app.repositories.review_repo import ReviewRepository
from app.repositories.user_repo import UserRepository
from app.services.notification_service import NotificationService


class ReviewService:
    def __init__(
        self,
        review_repo: ReviewRepository,
        booking_repo: BookingRepository,
        user_repo: UserRepository,
        notification_service: NotificationService,
    ) -> None:
        self.review_repo = review_repo
        self.booking_repo = booking_repo
        self.user_repo = user_repo
        self.notification_service = notification_service

    def create_review(
        self,
        db: Session,
        reviewer: User,
        trip_id: UUID,
        reviewee_id: UUID,
        rating: int,
        comment: str | None,
    ) -> Review:
        booking = self.booking_repo.get_by_trip_and_passenger(db, trip_id, reviewer.id)
        if not booking or booking.status != BookingStatus.COMPLETED:
            raise ValueError("Review allowed only after trip completion")
        reviewee = self.user_repo.get_by_id(db, reviewee_id)
        if not reviewee:
            raise ValueError("Reviewee not found")
        review = Review(
            trip_id=trip_id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            rating=rating,
            comment=comment,
        )
        saved = self.review_repo.create(db, review)
        new_count = reviewee.rating_count + 1
        new_avg = ((float(reviewee.rating_avg) * reviewee.rating_count) + rating) / new_count
        reviewee.rating_count = new_count
        reviewee.rating_avg = round(new_avg, 2)
        self.user_repo.update(db, reviewee)
        self.notification_service.create_notification(
            db,
            reviewee.id,
            NotificationType.REVIEW_RECEIVED,
            "New review",
            f"{reviewer.first_name or 'Passenger'} left you a review.",
        )
        return saved

    def list_reviews(self, db: Session, user_id: UUID) -> list[Review]:
        return self.review_repo.list_by_user(db, user_id)
