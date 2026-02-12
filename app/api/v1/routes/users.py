"""User routes."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.dependencies import get_current_user, get_db
from app.repositories.booking_repo import BookingRepository
from app.repositories.user_repo import UserRepository
from app.schemas.user import (
    PhoneNumberResponse,
    PhoneVerificationRequest,
    PhoneVerificationResponse,
    PlaylistResponse,
    PromoItem,
    PromoListResponse,
    ReferralResponse,
    UserPrivateResponse,
    UserPublicResponse,
    UserUpdate,
)
from app.services.user_service import UserService

router = APIRouter()
user_service = UserService(UserRepository(), BookingRepository())


@router.get("/me", response_model=UserPrivateResponse)
def get_me(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return user_service.get_user(db, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/me", response_model=UserPrivateResponse)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        user = user_service.update_user(db, current_user, payload.model_dump())
        db.commit()
        return user
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/me/avatar", response_model=UserPrivateResponse)
async def upload_avatar(
    avatar: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        content = await avatar.read()
        user = user_service.update_avatar(db, current_user, content, avatar.content_type)
        db.commit()
        return user
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/me/vehicle/photo", response_model=UserPrivateResponse)
async def upload_vehicle_photo(
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        content = await photo.read()
        user = user_service.update_vehicle_photo(db, current_user, content, photo.content_type)
        db.commit()
        return user
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/me/phone/request", response_model=PhoneVerificationResponse)
def request_phone_verification(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        code = user_service.request_phone_verification(db, current_user)
        db.commit()
        return PhoneVerificationResponse(status="sent", code=code)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/me/phone/verify", response_model=UserPrivateResponse)
def verify_phone(
    payload: PhoneVerificationRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        user = user_service.verify_phone(db, current_user, payload.code)
        db.commit()
        return user
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/playlist", response_model=PlaylistResponse)
def get_playlist():
    try:
        url = user_service.get_playlist_url()
        return PlaylistResponse(url=url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/promos", response_model=PromoListResponse)
def list_promos():
    items = [PromoItem(**promo) for promo in user_service.list_promos()]
    return PromoListResponse(items=items)


@router.get("/promos/student", response_model=PromoItem)
def get_student_promo():
    try:
        return PromoItem(**user_service.get_student_promo())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/me/referral", response_model=ReferralResponse)
def get_referral(
    current_user=Depends(get_current_user),
):
    try:
        url = user_service.get_referral_url(current_user)
        return ReferralResponse(url=url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{user_id}", response_model=UserPublicResponse)
def get_public_profile(user_id: UUID, db: Session = Depends(get_db)):
    try:
        return user_service.get_user(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{user_id}/phone", response_model=PhoneNumberResponse)
def get_user_phone(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        phone_number = user_service.get_phone_for_driver(db, current_user, user_id)
        return PhoneNumberResponse(phone_number=phone_number)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
