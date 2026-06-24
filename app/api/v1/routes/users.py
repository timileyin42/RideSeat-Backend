"""User routes."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.dependencies import get_current_user, get_db
from app.repositories.booking_repo import BookingRepository
from app.repositories.user_repo import UserRepository
from app.schemas.base import DataResponse
from app.schemas.user import (
    OnboardingRequest,
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
from app.services.email_service import EmailService
from app.services.user_service import UserService
from app.services.vision_service import VisionService

router = APIRouter()
user_service = UserService(UserRepository(), BookingRepository())
email_service = EmailService()
vision_service = VisionService()


@router.get("/me", response_model=DataResponse[UserPrivateResponse])
def get_me(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return DataResponse(data=user_service.get_user(db, current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/me", response_model=DataResponse[UserPrivateResponse])
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        user = user_service.update_user(db, current_user, payload.model_dump())
        db.commit()
        return DataResponse(data=user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/me/onboarding", response_model=DataResponse[UserPrivateResponse])
def complete_onboarding(
    payload: OnboardingRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Set name after email verification. Called once during the onboarding flow."""
    try:
        user = user_service.update_user(db, current_user, payload.model_dump())
        db.commit()
        return DataResponse(data=user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/me/avatar", response_model=DataResponse[UserPrivateResponse])
async def upload_avatar(
    avatar: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        content = await avatar.read()
        user = user_service.update_avatar(db, current_user, content, avatar.content_type)
        db.commit()
        return DataResponse(data=user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/me/vehicle/photo", response_model=DataResponse[UserPrivateResponse])
async def upload_vehicle_photo(
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        content = await photo.read()
        user = user_service.update_vehicle_photo(db, current_user, content, photo.content_type)
        db.commit()
        return DataResponse(data=user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/me/phone/request", response_model=DataResponse[PhoneVerificationResponse])
def request_phone_verification(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        channel = user_service.request_phone_verification(db, current_user)
        db.commit()
        return DataResponse(data=PhoneVerificationResponse(status="sent", channel=channel))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/me/phone/verify", response_model=DataResponse[UserPrivateResponse])
def verify_phone(
    payload: PhoneVerificationRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        user = user_service.verify_phone(db, current_user, payload.code)
        db.commit()
        return DataResponse(data=user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/playlist", response_model=DataResponse[PlaylistResponse])
def get_playlist():
    try:
        url = user_service.get_playlist_url()
        return DataResponse(data=PlaylistResponse(url=url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/promos", response_model=DataResponse[PromoListResponse])
def list_promos():
    items = [PromoItem(**promo) for promo in user_service.list_promos()]
    return DataResponse(data=PromoListResponse(items=items))


@router.get("/promos/student", response_model=DataResponse[PromoItem])
def get_student_promo():
    try:
        return DataResponse(data=PromoItem(**user_service.get_student_promo()))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/me/referral", response_model=DataResponse[ReferralResponse])
def get_referral(
    current_user=Depends(get_current_user),
):
    try:
        url = user_service.get_referral_url(current_user)
        return DataResponse(data=ReferralResponse(url=url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{user_id}", response_model=DataResponse[UserPublicResponse])
def get_public_profile(user_id: UUID, db: Session = Depends(get_db)):
    try:
        return DataResponse(data=user_service.get_user(db, user_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/me/verification/driver-licence", response_model=DataResponse[UserPrivateResponse])
async def upload_driver_licence(
    licence_number: str = Form(...),
    photo_front: UploadFile = File(...),
    photo_back: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        front_content = await photo_front.read()
        back_content = await photo_back.read() if photo_back else None
        back_type = photo_back.content_type if photo_back else None
        user = user_service.submit_driver_license(
            db, current_user, licence_number,
            front_content, photo_front.content_type,
            email_service, vision_service,
            back_content=back_content, back_content_type=back_type,
        )
        db.commit()
        return DataResponse(data=user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/me/verification/selfie", response_model=DataResponse[UserPrivateResponse])
async def upload_selfie(
    selfie: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        content = await selfie.read()
        user = user_service.submit_selfie(db, current_user, content, selfie.content_type)
        db.commit()
        return DataResponse(data=user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/me/verification/id-document", response_model=DataResponse[UserPrivateResponse])
async def upload_id_document(
    document: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        content = await document.read()
        user = user_service.submit_id_document(db, current_user, content, document.content_type)
        db.commit()
        return DataResponse(data=user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{user_id}/phone", response_model=DataResponse[PhoneNumberResponse])
def get_user_phone(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        phone_number = user_service.get_phone_for_driver(db, current_user, user_id)
        return DataResponse(data=PhoneNumberResponse(phone_number=phone_number))
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.delete("/me", status_code=204)
def delete_my_account(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        user_service.delete_account(db, current_user)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
