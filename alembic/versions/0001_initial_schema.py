"""Initial schema — all tables for PostgreSQL.

Revision ID: 0001
Revises:
Create Date: 2026-05-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


# ── PostgreSQL ENUM types ──────────────────────────────────────────────────────

userrole = sa.Enum("DRIVER", "PASSENGER", "BOTH", name="userrole")
gender = sa.Enum("MALE", "FEMALE", "NON_BINARY", "OTHER", "PREFER_NOT_TO_SAY", name="gender")
smokingpref = sa.Enum("SMOKING", "NO_SMOKING", name="smokingpreference")
chatpref = sa.Enum("QUIET", "OK_TO_CHAT", "CHATTY", name="chatpreference")
luggagesize = sa.Enum("NO_LUGGAGE", "SMALL", "MEDIUM", "LARGE", name="luggagesize")
bookingstatus = sa.Enum("PENDING", "CONFIRMED", "CANCELLED", "COMPLETED", name="bookingstatus")
paymentstatus = sa.Enum(
    "REQUIRES_PAYMENT_METHOD", "REQUIRES_CONFIRMATION", "PROCESSING", "SUCCEEDED", "FAILED",
    name="paymentstatus",
)
deviceplatform = sa.Enum("ios", "android", "web", name="deviceplatform")
notiftype = sa.Enum(
    "BOOKING_REQUEST", "BOOKING_CANCELLED", "TRIP_COMPLETED", "MESSAGE_RECEIVED", "REVIEW_RECEIVED",
    name="notificationtype",
)
identitystatus = sa.Enum("PENDING", "APPROVED", "REJECTED", name="identityverificationstatus")


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(20), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        # Encrypted at rest (Text stores the Fernet ciphertext)
        sa.Column("phone_number", sa.Text(), nullable=True),
        sa.Column("is_phone_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("phone_verification_token", sa.String(255), nullable=True),
        sa.Column("phone_verification_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("profile_photo_url", sa.String(500), nullable=True),
        # Encrypted at rest
        sa.Column("payment_details", sa.Text(), nullable=True),
        sa.Column("role", userrole, nullable=False, server_default="PASSENGER"),
        sa.Column("bio", sa.String(300), nullable=True),
        sa.Column("age_range", sa.String(50), nullable=True),
        # Encrypted at rest (stored as ISO date string then Fernet-encrypted)
        sa.Column("date_of_birth", sa.Text(), nullable=True),
        sa.Column("gender", gender, nullable=True),
        sa.Column("smoking_preference", smokingpref, nullable=True),
        sa.Column("chat_preference", chatpref, nullable=True),
        sa.Column("notify_push", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_sms", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_email", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_in_app", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("marketing_emails", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("vehicle_photo_url", sa.String(500), nullable=True),
        sa.Column("vehicle_make", sa.String(100), nullable=True),
        sa.Column("vehicle_model", sa.String(100), nullable=True),
        sa.Column("vehicle_type", sa.String(100), nullable=True),
        sa.Column("vehicle_color", sa.String(50), nullable=True),
        sa.Column("vehicle_year", sa.Integer(), nullable=True),
        sa.Column("vehicle_plate", sa.String(50), nullable=True),
        sa.Column("luggage_size", luggagesize, nullable=True),
        sa.Column("back_seat_max", sa.Integer(), nullable=True),
        sa.Column("has_winter_tires", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("allows_bikes", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("allows_skis", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("allows_snowboards", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("allows_pets", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("rating_avg", sa.Numeric(3, 2), nullable=False, server_default="0"),
        sa.Column("rating_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trips_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("selfie_url", sa.String(500), nullable=True),
        sa.Column("id_document_url", sa.String(500), nullable=True),
        sa.Column("driver_license_url", sa.String(500), nullable=True),
        # Encrypted at rest
        sa.Column("driver_license_number", sa.Text(), nullable=True),
        sa.Column("identity_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("identity_verification_status", identitystatus, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── vehicles ───────────────────────────────────────────────────────────────
    op.create_table(
        "vehicles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("make", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("type", sa.String(100), nullable=True),
        sa.Column("color", sa.String(50), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("plate", sa.String(50), nullable=False),
        sa.Column("back_seat_max", sa.Integer(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vehicles_user_id", "vehicles", ["user_id"])

    # ── trips ──────────────────────────────────────────────────────────────────
    op.create_table(
        "trips",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("driver_id", sa.UUID(), nullable=False),
        sa.Column("vehicle_id", sa.UUID(), nullable=True),
        sa.Column("origin_city", sa.String(120), nullable=False),
        sa.Column("destination_city", sa.String(120), nullable=False),
        sa.Column("origin_address", sa.String(255), nullable=True),
        sa.Column("destination_address", sa.String(255), nullable=True),
        sa.Column("origin_lat", sa.Float(), nullable=True),
        sa.Column("origin_lng", sa.Float(), nullable=True),
        sa.Column("destination_lat", sa.Float(), nullable=True),
        sa.Column("destination_lng", sa.Float(), nullable=True),
        sa.Column("departure_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("estimated_arrival_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_seats", sa.Integer(), nullable=False),
        sa.Column("price_per_seat", sa.Numeric(10, 2), nullable=False),
        sa.Column("toll_fee", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("vehicle_make", sa.String(100), nullable=False),
        sa.Column("vehicle_model", sa.String(100), nullable=False),
        sa.Column("vehicle_color", sa.String(50), nullable=False),
        sa.Column("instant_booking", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("music_allowed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("pets_allowed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("smoking_allowed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("air_conditioning", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("minimal_luggage", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("luggage_allowed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("requires_passport", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("stops", sa.JSON(), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("is_cancelled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["driver_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trips_driver_id", "trips", ["driver_id"])
    op.create_index("ix_trips_vehicle_id", "trips", ["vehicle_id"])

    # ── bookings ───────────────────────────────────────────────────────────────
    op.create_table(
        "bookings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("passenger_id", sa.UUID(), nullable=False),
        sa.Column("seats", sa.Integer(), nullable=False),
        sa.Column("status", bookingstatus, nullable=False, server_default="PENDING"),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["passenger_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bookings_trip_id", "bookings", ["trip_id"])
    op.create_index("ix_bookings_passenger_id", "bookings", ["passenger_id"])

    # ── messages ───────────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("booking_id", sa.UUID(), nullable=False),
        sa.Column("sender_id", sa.UUID(), nullable=False),
        sa.Column("content", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_booking_id", "messages", ["booking_id"])
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"])

    # ── payments ───────────────────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("booking_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("platform_fee", sa.Numeric(10, 2), nullable=False),
        sa.Column("payout_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", paymentstatus, nullable=False),
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
        sa.Column("stripe_charge_id", sa.String(255), nullable=True),
        sa.Column("stripe_transfer_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_booking_id", "payments", ["booking_id"])

    # ── reviews ────────────────────────────────────────────────────────────────
    op.create_table(
        "reviews",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("reviewer_id", sa.UUID(), nullable=False),
        sa.Column("reviewee_id", sa.UUID(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewee_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reviews_trip_id", "reviews", ["trip_id"])
    op.create_index("ix_reviews_reviewer_id", "reviews", ["reviewer_id"])
    op.create_index("ix_reviews_reviewee_id", "reviews", ["reviewee_id"])

    # ── devices ────────────────────────────────────────────────────────────────
    op.create_table(
        "devices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("device_token", sa.String(500), nullable=False),
        sa.Column("platform", deviceplatform, nullable=False),
        sa.Column("device_name", sa.String(120), nullable=True),
        sa.Column("app_version", sa.String(50), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_token"),
    )
    op.create_index("ix_devices_user_id", "devices", ["user_id"])
    op.create_index("ix_devices_device_token", "devices", ["device_token"], unique=True)

    # ── notifications ──────────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("notification_type", notiftype, nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("body", sa.String(500), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("devices")
    op.drop_table("reviews")
    op.drop_table("payments")
    op.drop_table("messages")
    op.drop_table("bookings")
    op.drop_table("trips")
    op.drop_table("vehicles")
    op.drop_table("users")

    # Drop PostgreSQL ENUM types
    identitystatus.drop(op.get_bind())
    notiftype.drop(op.get_bind())
    deviceplatform.drop(op.get_bind())
    paymentstatus.drop(op.get_bind())
    bookingstatus.drop(op.get_bind())
    luggagesize.drop(op.get_bind())
    chatpref.drop(op.get_bind())
    smokingpref.drop(op.get_bind())
    gender.drop(op.get_bind())
    userrole.drop(op.get_bind())
