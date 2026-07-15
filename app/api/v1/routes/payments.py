"""Payment routes."""

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.dependencies import get_current_user, get_db, rate_limit
from app.repositories.booking_repo import BookingRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.user_repo import UserRepository
from app.schemas.base import DataResponse
from app.schemas.payment import (
    ConnectDocumentResponse,
    ConnectOnboardRequest,
    ConnectOnboardResponse,
    ConnectStatusResponse,
    PaymentIntentCreate,
    PaymentResponse,
    PayoutRequestResponse,
)
from app.services.payment_service import PaymentService

router = APIRouter()
payment_service = PaymentService(PaymentRepository(), BookingRepository(), TripRepository(), UserRepository())


@router.post("/intent", response_model=DataResponse[PaymentResponse])
def create_payment_intent(
    payload: PaymentIntentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit("payments_intent", limit=5, window_seconds=60)),
):
    try:
        payment = payment_service.create_payment_intent(db, UUID(payload.booking_id), current_user.id)
        db.commit()
        return DataResponse(data=payment)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    try:
        payload = await request.body()
        payment_service.handle_webhook(db, payload, stripe_signature)
        db.commit()
        return {"received": True}
    except ValueError as exc:
        db.rollback()
        if "Unhandled event type" in str(exc):
            return {"received": True}
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/history", response_model=DataResponse[list[PaymentResponse]])
def list_payment_history(
    period: str = Query(pattern="^(7d|30d|6m|1y)$"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit("payments_history", limit=20, window_seconds=60)),
):
    try:
        return DataResponse(data=payment_service.list_payment_history(db, current_user.id, period))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/connect/onboard", response_model=DataResponse[ConnectOnboardResponse])
def connect_onboard(
    payload: ConnectOnboardRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit("connect_onboard", limit=3, window_seconds=60)),
):
    """
    Submit driver personal + bank details directly to Stripe (Custom account).
    No redirect — everything happens in your app screens.
    """
    if not payload.tos_accepted:
        raise HTTPException(status_code=400, detail="You must accept the Terms of Service")
    client_ip = request.client.host if request.client else "unknown"
    try:
        result = payment_service.create_connect_account(db, current_user.id, payload.model_dump(), client_ip)
        db.commit()
        return DataResponse(data=result)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/connect/document", response_model=DataResponse[ConnectDocumentResponse])
async def upload_document(
    file: UploadFile = File(...),
    purpose: str = Query(pattern="^(identity_document_front|identity_document_back)$"),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit("connect_document", limit=5, window_seconds=60)),
):
    """
    Upload one side of a government ID to Stripe.
    Call once for front, once for back (if driving licence).
    Returns a file_id — pass both to /connect/attach-document.
    """
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB.")
    try:
        result = payment_service.upload_identity_document(
            current_user.id, contents, file.filename or "document.jpg", purpose
        )
        return DataResponse(data=result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/connect/attach-document", response_model=DataResponse[dict])
def attach_document(
    front_file_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    back_file_id: str | None = None,
):
    """
    Attach uploaded document file IDs to the driver's Stripe account.
    Pass front_file_id always; back_file_id only for driving licence.
    """
    try:
        payment_service.attach_identity_document(db, current_user.id, front_file_id, back_file_id)
        return DataResponse(data={"message": "Identity document attached successfully"})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/connect/payout-history", response_model=DataResponse[list[PaymentResponse]])
def driver_payout_history(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Driver's full transaction history — all earnings from their trips."""
    payments = payment_service.payment_repo.list_payouts_by_driver(db, current_user.id)
    return DataResponse(data=payments)


@router.post("/connect/request-payout", response_model=DataResponse[PayoutRequestResponse])
def request_payout(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit("request_payout", limit=5, window_seconds=60)),
):
    """Driver manually requests payout for all completed, unpaid earnings."""
    try:
        result = payment_service.request_payout(db, current_user.id)
        db.commit()
        return DataResponse(data=result)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/connect/status", response_model=DataResponse[ConnectStatusResponse])
def connect_status(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Check whether the driver's Stripe Connect account is fully onboarded."""
    try:
        return DataResponse(data=payment_service.get_connect_status(db, current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{booking_id}", response_model=DataResponse[PaymentResponse])
def get_payment_status(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return DataResponse(data=payment_service.get_payment_status_for_user(db, booking_id, current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
