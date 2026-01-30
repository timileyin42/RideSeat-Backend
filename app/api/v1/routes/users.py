"""User routes."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.dependencies import get_current_user, get_db
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserPrivateResponse, UserPublicResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter()
user_service = UserService(UserRepository())


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


@router.get("/{user_id}", response_model=UserPublicResponse)
def get_public_profile(user_id: UUID, db: Session = Depends(get_db)):
    try:
        return user_service.get_user(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
