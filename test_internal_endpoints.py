import argparse
import json
from datetime import datetime, timedelta, timezone
from urllib import error, parse, request

from app.utils.local_testing import ensure_schema, upsert_verified_user
from app.core.constants import BookingStatus, NotificationType, PaymentStatus, UserRole
from app.core.database import SessionLocal
from app.models.booking import Booking
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.user import User


def _parse_body(raw: bytes) -> object:
    text = raw.decode("utf-8") if raw else ""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _request(method: str, url: str, token: str | None = None, payload: dict | None = None) -> tuple[int, object]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req) as response:
            return response.status, _parse_body(response.read())
    except error.HTTPError as exc:
        return exc.code, _parse_body(exc.read())


def _log_result(name: str, status: int, data: object) -> None:
    ok = 200 <= status < 300
    mark = "OK" if ok else "FAIL"
    print({"step": name, "status": status, "result": mark, "data": data})


def _ensure_admin(email: str, password: str) -> User:
    upsert_verified_user(
        email=email,
        password=password,
        first_name="Admin",
        last_name="User",
        phone_number=None,
        role=UserRole.DRIVER,
    )
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == email).first()
        if not admin:
            raise SystemExit({"step": "admin_seed", "status": "missing_admin"})
        if not admin.is_admin:
            admin.is_admin = True
            db.add(admin)
            db.commit()
            db.refresh(admin)
        return admin
    finally:
        db.close()


def _ensure_booking(trip_id: str, passenger_id: str, status: BookingStatus) -> Booking:
    db = SessionLocal()
    try:
        booking = (
            db.query(Booking)
            .filter(Booking.trip_id == trip_id, Booking.passenger_id == passenger_id, Booking.status == status)
            .first()
        )
        if booking:
            return booking
        booking = Booking(
            trip_id=trip_id,
            passenger_id=passenger_id,
            seats=1,
            status=status,
            total_amount=5000,
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        return booking
    finally:
        db.close()


def _ensure_payment(booking_id: str, amount: float) -> Payment:
    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_id == booking_id).first()
        if payment:
            return payment
        platform_fee = round(amount * 0.1, 2)
        payout_amount = round(amount - platform_fee, 2)
        payment = Payment(
            booking_id=booking_id,
            amount=amount,
            platform_fee=platform_fee,
            payout_amount=payout_amount,
            status=PaymentStatus.REQUIRES_PAYMENT_METHOD,
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        return payment
    finally:
        db.close()


def _ensure_notification(user_id: str) -> Notification:
    db = SessionLocal()
    try:
        notification = (
            db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.notification_type == NotificationType.MESSAGE_RECEIVED)
            .first()
        )
        if notification:
            return notification
        notification = Notification(
            user_id=user_id,
            notification_type=NotificationType.MESSAGE_RECEIVED,
            title="Test notification",
            body="Internal test notification",
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", default="tester@example.com")
    parser.add_argument("--password", default="pass1234")
    parser.add_argument("--passenger-email", default="passenger@example.com")
    parser.add_argument("--passenger-password", default="pass1234")
    parser.add_argument("--admin-email", default="admin@example.com")
    parser.add_argument("--admin-password", default="pass1234")
    args = parser.parse_args()

    ensure_schema()
    driver_user = upsert_verified_user(
        email=args.email,
        password=args.password,
        first_name="Driver",
        last_name="User",
        phone_number=None,
        role=UserRole.DRIVER,
    )
    passenger_user = upsert_verified_user(
        email=args.passenger_email,
        password=args.passenger_password,
        first_name="Passenger",
        last_name="User",
        phone_number="2348012345678",
        role=UserRole.PASSENGER,
    )
    admin_user = _ensure_admin(args.admin_email, args.admin_password)

    status, root = _request("GET", f"{args.base_url}/")
    _log_result("root", status, root)

    status, health = _request("GET", f"{args.base_url}/health")
    _log_result("health", status, health)

    status, data = _request(
        "POST",
        f"{args.base_url}/api/v1/auth/login",
        payload={"email": args.email, "password": args.password},
    )
    if status != 200 or not isinstance(data, dict):
        raise SystemExit({"step": "login", "status": status, "data": data})

    token = data["access_token"]
    status, passenger_login = _request(
        "POST",
        f"{args.base_url}/api/v1/auth/login",
        payload={"email": args.passenger_email, "password": args.passenger_password},
    )
    if status != 200 or not isinstance(passenger_login, dict):
        raise SystemExit({"step": "passenger_login", "status": status, "data": passenger_login})
    passenger_token = passenger_login["access_token"]

    status, admin_login = _request(
        "POST",
        f"{args.base_url}/api/v1/auth/login",
        payload={"email": args.admin_email, "password": args.admin_password},
    )
    if status != 200 or not isinstance(admin_login, dict):
        raise SystemExit({"step": "admin_login", "status": status, "data": admin_login})
    admin_token = admin_login["access_token"]

    status, me = _request("GET", f"{args.base_url}/api/v1/users/me", token=token)
    _log_result("users_me", status, me)

    user_id = me.get("id") if isinstance(me, dict) else None
    status, me_update = _request(
        "PUT",
        f"{args.base_url}/api/v1/users/me",
        token=token,
        payload={"bio": "Internal test bio", "phone_number": "1234567890"},
    )
    _log_result("users_update_me", status, me_update)

    status, phone_request = _request(
        "POST",
        f"{args.base_url}/api/v1/users/me/phone/request",
        token=token,
    )
    _log_result("users_phone_request", status, phone_request)

    phone_code = phone_request.get("code") if isinstance(phone_request, dict) else None
    if phone_code:
        status, phone_verify = _request(
            "POST",
            f"{args.base_url}/api/v1/users/me/phone/verify",
            token=token,
            payload={"code": phone_code},
        )
        _log_result("users_phone_verify", status, phone_verify)

    status, playlist = _request("GET", f"{args.base_url}/api/v1/users/playlist")
    _log_result("users_playlist", status, playlist)

    status, promos = _request("GET", f"{args.base_url}/api/v1/users/promos")
    _log_result("users_promos", status, promos)

    status, student = _request("GET", f"{args.base_url}/api/v1/users/promos/student")
    _log_result("users_promos_student", status, student)

    status, referral = _request("GET", f"{args.base_url}/api/v1/users/me/referral", token=token)
    _log_result("users_referral", status, referral)

    if user_id:
        status, public_profile = _request("GET", f"{args.base_url}/api/v1/users/{user_id}")
        _log_result("users_public_profile", status, public_profile)

        status, reviews = _request("GET", f"{args.base_url}/api/v1/reviews/user/{user_id}")
        _log_result("reviews_list", status, reviews)

    status, passenger_phone = _request(
        "GET",
        f"{args.base_url}/api/v1/users/{passenger_user.id}/phone",
        token=token,
    )
    _log_result("users_phone", status, passenger_phone)

    departure_date = datetime.now(tz=timezone.utc).date().isoformat()
    search_query = parse.urlencode(
        {"origin_city": "Lagos", "destination_city": "Ibadan", "departure_date": departure_date, "passengers": 1}
    )
    status, search = _request("GET", f"{args.base_url}/api/v1/trips/search?{search_query}")
    _log_result("trips_search", status, search)

    departure_time = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
    status, trip = _request(
        "POST",
        f"{args.base_url}/api/v1/trips",
        token=token,
        payload={
            "origin_city": "Lagos",
            "destination_city": "Ibadan",
            "departure_time": departure_time,
            "available_seats": 3,
            "price_per_seat": 5000,
            "toll_fee": 0,
            "vehicle_make": "Toyota",
            "vehicle_model": "Corolla",
            "vehicle_color": "Blue",
            "luggage_allowed": True,
            "notes": "Internal test trip",
        },
    )
    _log_result("trips_create", status, trip)

    trip_id = trip.get("id") if isinstance(trip, dict) else None
    if trip_id:
        booking_pending = _ensure_booking(trip_id, str(passenger_user.id), BookingStatus.PENDING)

        status, trip_details = _request("GET", f"{args.base_url}/api/v1/trips/{trip_id}")
        _log_result("trips_get", status, trip_details)

        status, trip_update = _request(
            "PUT",
            f"{args.base_url}/api/v1/trips/{trip_id}",
            token=token,
            payload={"notes": "Internal test trip updated"},
        )
        _log_result("trips_update", status, trip_update)

        status, booking_status = _request(
            "PATCH",
            f"{args.base_url}/api/v1/bookings/{booking_pending.id}/status",
            token=token,
            payload={"status": "CONFIRMED"},
        )
        _log_result("bookings_status", status, booking_status)

        status, booking_cancel = _request(
            "POST",
            f"{args.base_url}/api/v1/bookings/{booking_pending.id}/cancel",
            token=passenger_token,
        )
        _log_result("bookings_cancel", status, booking_cancel)

        _ensure_payment(str(booking_pending.id), 5000)

        status, payment_status = _request(
            "GET",
            f"{args.base_url}/api/v1/payments/{booking_pending.id}",
            token=token,
        )
        _log_result("payments_status", status, payment_status)

        status, trip_cancel = _request(
            "DELETE",
            f"{args.base_url}/api/v1/trips/{trip_id}",
            token=token,
        )
        _log_result("trips_cancel", status, trip_cancel)

    status, trip_review = _request(
        "POST",
        f"{args.base_url}/api/v1/trips",
        token=token,
        payload={
            "origin_city": "Abuja",
            "destination_city": "Kaduna",
            "departure_time": (datetime.now(tz=timezone.utc) + timedelta(hours=5)).isoformat(),
            "available_seats": 2,
            "price_per_seat": 4000,
            "toll_fee": 0,
            "vehicle_make": "Honda",
            "vehicle_model": "Civic",
            "vehicle_color": "White",
            "luggage_allowed": True,
            "notes": "Internal test trip review",
        },
    )
    _log_result("trips_create_review", status, trip_review)

    review_trip_id = trip_review.get("id") if isinstance(trip_review, dict) else None
    if review_trip_id:
        booking_completed = _ensure_booking(review_trip_id, str(passenger_user.id), BookingStatus.COMPLETED)

        status, message_send = _request(
            "POST",
            f"{args.base_url}/api/v1/messages/{booking_completed.id}",
            token=passenger_token,
            payload={"content": "Hello driver, this is a test message"},
        )
        _log_result("messages_send", status, message_send)

        status, messages_list = _request(
            "GET",
            f"{args.base_url}/api/v1/messages/{booking_completed.id}",
            token=token,
        )
        _log_result("messages_list", status, messages_list)

        status, review_create = _request(
            "POST",
            f"{args.base_url}/api/v1/reviews",
            token=passenger_token,
            payload={
                "trip_id": review_trip_id,
                "reviewee_id": str(driver_user.id),
                "rating": 5,
                "comment": "Great ride",
            },
        )
        _log_result("reviews_create", status, review_create)

    status, bookings = _request("GET", f"{args.base_url}/api/v1/bookings/me", token=token)
    _log_result("bookings_me", status, bookings)

    status, driver_bookings = _request("GET", f"{args.base_url}/api/v1/bookings/driver", token=token)
    _log_result("bookings_driver", status, driver_bookings)

    status, payment_history = _request(
        "GET",
        f"{args.base_url}/api/v1/payments/history?period=7d",
        token=token,
    )
    _log_result("payments_history", status, payment_history)

    device_token = f"internal-test-token-{int(datetime.now(tz=timezone.utc).timestamp())}"
    new_device_token = f"{device_token}-new"
    status, device = _request(
        "POST",
        f"{args.base_url}/api/v1/notifications/devices/register",
        token=token,
        payload={"device_token": device_token, "platform": "android"},
    )
    _log_result("notifications_register_device", status, device)

    status, updated_device = _request(
        "POST",
        f"{args.base_url}/api/v1/devices/update-token",
        token=token,
        payload={
            "old_device_token": device_token,
            "new_device_token": new_device_token,
            "platform": "android",
        },
    )
    _log_result("devices_update_token", status, updated_device)

    status, notifications = _request("GET", f"{args.base_url}/api/v1/notifications", token=token)
    _log_result("notifications_list", status, notifications)

    notification = _ensure_notification(str(driver_user.id))
    status, notification_read = _request(
        "POST",
        f"{args.base_url}/api/v1/notifications/{notification.id}/read",
        token=token,
    )
    _log_result("notifications_read", status, notification_read)

    status, admin_users = _request("GET", f"{args.base_url}/api/v1/admin/users", token=admin_token)
    _log_result("admin_users", status, admin_users)

    status, admin_metrics = _request("GET", f"{args.base_url}/api/v1/admin/metrics", token=admin_token)
    _log_result("admin_metrics", status, admin_metrics)

    status, admin_trips = _request("GET", f"{args.base_url}/api/v1/admin/trips", token=admin_token)
    _log_result("admin_trips", status, admin_trips)

    status, admin_bookings = _request("GET", f"{args.base_url}/api/v1/admin/bookings", token=admin_token)
    _log_result("admin_bookings", status, admin_bookings)

    if review_trip_id:
        booking_for_admin = _ensure_booking(review_trip_id, str(passenger_user.id), BookingStatus.COMPLETED)
        status, admin_resolve = _request(
            "POST",
            f"{args.base_url}/api/v1/admin/bookings/{booking_for_admin.id}/resolve",
            token=admin_token,
            payload={"status": "CANCELLED"},
        )
        _log_result("admin_resolve_booking", status, admin_resolve)


if __name__ == "__main__":
    main()
