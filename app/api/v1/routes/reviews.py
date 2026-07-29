"""Review routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.dependencies import get_current_user, get_db
from app.repositories.booking_repo import BookingRepository
from app.repositories.device_repo import DeviceRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.review_repo import ReviewRepository
from app.repositories.user_repo import UserRepository
from app.schemas.base import DataResponse
from app.schemas.review import ReviewCreate, ReviewResponse
from app.services.review_service import ReviewService
from app.services.notification_service import NotificationService

router = APIRouter()
notification_service = NotificationService(DeviceRepository(), NotificationRepository(), UserRepository())
review_service = ReviewService(ReviewRepository(), BookingRepository(), UserRepository(), notification_service)


@router.post("", response_model=DataResponse[ReviewResponse], status_code=201)
def create_review(
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        review = review_service.create_review(
            db,
            reviewer=current_user,
            trip_id=UUID(payload.trip_id),
            reviewee_id=UUID(payload.reviewee_id),
            rating=payload.rating,
            comment=payload.comment,
        )
        db.commit()
        return DataResponse(data=review)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected error in create_review")
        raise HTTPException(status_code=500, detail="Review processing error") from exc


@router.get("/user/{user_id}", response_model=DataResponse[list[ReviewResponse]])
def list_reviews(user_id: UUID, db: Session = Depends(get_db)):
    return DataResponse(data=review_service.list_reviews(db, user_id))
