# Rideway Frontend API Handover

**Base URL:** `https://api.rideway.co.uk/api/v1`  
**Auth:** Bearer token — `Authorization: Bearer <access_token>`  
**Response envelope:** Every response is wrapped as `{ "data": <payload> }` — always unwrap `.data`.

---

## Table of Contents

1. [Response Shape](#1-response-shape)
2. [Authentication](#2-authentication)
3. [User Profile](#3-user-profile)
4. [Phone Verification](#4-phone-verification)
5. [Identity Verification (KYC)](#5-identity-verification-kyc)
6. [Vehicles](#6-vehicles)
7. [Trips](#7-trips)
8. [Bookings](#8-bookings)
9. [Payments & Stripe](#9-payments--stripe)
10. [Driver Payout (Stripe Connect)](#10-driver-payout-stripe-connect)
11. [Notifications & Devices](#11-notifications--devices)
12. [Messaging](#12-messaging)
13. [Reviews](#13-reviews)
14. [Support Tickets](#14-support-tickets)
15. [Misc (Promos, Playlist, Referral)](#15-misc-promos-playlist-referral)
16. [Admin Dashboard](#16-admin-dashboard)
17. [Error Reference](#17-error-reference)
18. [Gap Log — Designs Without API](#18-gap-log--designs-without-api)

---

## 1. Response Shape

```json
// Success
{ "data": <payload> }

// Error
{ "detail": "Human-readable message" }
```

`data` is always the typed payload. Never read directly off the root.

---

## 2. Authentication

### Register
```
POST /auth/register
```
```json
{
  "email": "user@example.com",
  "password": "SecurePass1!",
  "first_name": "James",
  "last_name": "Harrison",
  "date_of_birth": "1995-04-20"
}
```
Returns: `AuthTokenResponse` — store `access_token` and `refresh_token`.  
The user's `is_email_verified` will be `false`. Send them to the OTP screen.

### Login
```
POST /auth/login
```
```json
{ "email": "user@example.com", "password": "SecurePass1!" }
```
Returns: `AuthTokenResponse`

### Verify Email
```
POST /auth/verify-email
```
```json
{ "email": "user@example.com", "token": "123456" }
```
Returns: fresh `AuthTokenResponse` — replace stored tokens.

### Resend OTP
```
POST /auth/resend-otp
```
```json
{ "email": "user@example.com" }
```
Returns: `{ "data": { "status": "sent" } }`  
Rate-limited: 3 per minute.

### Forgot Password
```
POST /auth/forgot-password
```
```json
{ "email": "user@example.com" }
```

### Reset Password
```
POST /auth/reset-password
```
```json
{ "email": "user@example.com", "token": "123456", "new_password": "NewPass1!" }
```

### Change Password (in-app)
```
POST /auth/change-password       [Auth required]
```
```json
{ "current_password": "OldPass1!", "new_password": "NewPass1!" }
```

### Refresh Token
```
POST /auth/refresh
```
```json
{ "refresh_token": "<refresh_token>" }
```
Returns: new `AuthTokenResponse`. Call this when a request returns 401.

### Google OAuth
```
POST /auth/google/mobile         ← use this one for the app
```
```json
{ "id_token": "<google_id_token>" }
```
Returns: `AuthTokenResponse`

### AuthTokenResponse shape
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "user": { ...UserPrivateResponse }
}
```

---

## 3. User Profile

### Get my profile
```
GET /users/me                    [Auth required]
```
Returns: `UserPrivateResponse`

### Update my profile
```
PUT /users/me                    [Auth required]
```
```json
{
  "first_name": "James",
  "last_name": "Harrison",
  "bio": "Friendly driver.",
  "title": "Mr"
}
```

### Onboarding (set name after email verify)
```
POST /users/me/onboarding        [Auth required]
```
```json
{ "first_name": "James", "last_name": "Harrison" }
```
Call once after the user verifies email, before they go to the home screen.

### Upload avatar
```
POST /users/me/avatar            [Auth required]
Content-Type: multipart/form-data
Field: avatar (image file)
```

### Get public profile
```
GET /users/{user_id}
```
Returns: `UserPublicResponse` (no email, no phone)

### Get driver phone number
```
GET /users/{user_id}/phone       [Auth required]
```
Only works if the caller has a confirmed booking with this driver. Use to show the "call driver" button.

### Delete account
```
DELETE /users/me                 [Auth required]
```
Returns: 204 No Content

### UserPrivateResponse shape
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "first_name": "James",
  "last_name": "Harrison",
  "profile_photo_url": "https://...",
  "bio": "...",
  "role": "PASSENGER",
  "rating_avg": 4.8,
  "trips_completed": 12,
  "is_email_verified": true,
  "is_phone_verified": true,
  "phone_number": "+447911123456",
  "payment_details": null,
  "licence_verified": false,
  "id_document_verified": false,
  "selfie_verified": false
}
```

---

## 4. Phone Verification

### Step 1 — Request OTP
```
POST /users/me/phone/request     [Auth optional]
```
```json
{ "phone_number": "+447911123456" }
```
Returns: `{ "data": { "status": "sent", "channel": "sms" } }`  
`channel` is always `"sms"` — show "We sent you an SMS".

### Step 2 — Verify OTP
```
POST /users/me/phone/verify      [Auth optional]
```
```json
{ "phone_number": "+447911123456", "code": "583017" }
```
Returns: `{ "data": { "verified": true, "phone_number": "+447...", "user": {...} } }`  
If `user` is present, replace stored user in state.

**Note:** UK numbers only (`+44...`). Nigerian numbers will fail with 422 — the app is UK-only.

---

## 5. Identity Verification (KYC)

All uploads are `multipart/form-data`.

### Upload Driver Licence
```
POST /users/me/verification/driver-licence    [Auth required]
```
Fields:
- `licence_number` (text) — e.g. `JONES753116SM9IJ`
- `photo_front` (file) — front of licence
- `photo_back` (file, optional) — back of licence

### Upload ID Document (passport / national ID)
```
POST /users/me/verification/id-document      [Auth required]
```
Fields:
- `document` (file)

### Upload Selfie
```
POST /users/me/verification/selfie           [Auth required]
```
Fields:
- `selfie` (file)

All three return updated `UserPrivateResponse`. After uploading, admin approves/rejects via admin routes (frontend doesn't need to call those).

---

## 6. Vehicles

```
POST   /vehicles                 [Auth] — add vehicle
GET    /vehicles                 [Auth] — list my vehicles
PUT    /vehicles/{id}            [Auth] — update vehicle
DELETE /vehicles/{id}            [Auth] — delete vehicle
PUT    /vehicles/{id}/default    [Auth] — set as default
```

### Add Vehicle body
```json
{
  "make": "Toyota",
  "model": "Prius",
  "color": "Silver",
  "year": 2021,
  "plate": "AB21 XYZ"
}
```

### VehicleResponse shape
```json
{
  "id": "uuid",
  "make": "Toyota",
  "model": "Prius",
  "color": "Silver",
  "year": 2021,
  "plate": "AB21 XYZ",
  "is_default": true
}
```

When creating a trip the driver can pass `vehicle_id` — the API copies make/model/color onto the trip automatically.

---

## 7. Trips

### Create Trip
```
POST /trips                      [Auth required]
```
```json
{
  "origin_city": "Manchester",
  "destination_city": "London",
  "origin_address": "Piccadilly Gardens, Manchester",
  "destination_address": "Victoria Coach Station, London",
  "origin_lat": 53.4808,
  "origin_lng": -2.2426,
  "destination_lat": 51.4934,
  "destination_lng": -0.1441,
  "departure_time": "2026-08-01T08:00:00Z",
  "estimated_duration_minutes": 210,
  "available_seats": 3,
  "price_per_seat": 25.00,
  "toll_fee": 0.00,
  "instant_booking": true,
  "booking_mode": "INSTANT",
  "vehicle_id": "uuid-optional",
  "notes": "Optional notes for passengers"
}
```
`booking_mode` values: `"INSTANT"` | `"REVIEW_REQUESTS"`  
`instant_booking: true` means passengers pay immediately; no driver approval step.

### Search Trips
```
GET /trips/search
```
Query params (all optional):
- `origin_city=Manchester`
- `destination_city=London`
- `departure_date=2026-08-01`  (YYYY-MM-DD)
- `passengers=2`  (1–6)
- `sort_by=departure_time|price|seats_remaining`
- `order=asc|desc`

No auth required.

### Get Trip
```
GET /trips/{trip_id}
```

### My Trips (as driver)
```
GET /trips/mine                  [Auth required]
```

### Update Trip
```
PUT /trips/{trip_id}             [Auth required]
```

### Cancel Trip
```
DELETE /trips/{trip_id}          [Auth required]
```

### Start Trip (driver only)
```
PATCH /trips/{trip_id}/start     [Auth required]
```
No body. Call when driver is departing.

### Complete Trip (driver only)
```
PATCH /trips/{trip_id}/complete  [Auth required]
```
No body. All confirmed bookings become COMPLETED and payouts are triggered automatically.

### TripResponse shape
```json
{
  "id": "uuid",
  "driver_id": "uuid",
  "driver": { ...UserPublicResponse },
  "origin_city": "Manchester",
  "destination_city": "London",
  "origin_address": "...",
  "destination_address": "...",
  "origin_lat": 53.4808,
  "origin_lng": -2.2426,
  "destination_lat": 51.4934,
  "destination_lng": -0.1441,
  "departure_time": "2026-08-01T08:00:00Z",
  "estimated_duration_minutes": 210,
  "estimated_arrival_time": "2026-08-01T11:30:00Z",
  "available_seats": 3,
  "seats_remaining": 1,
  "price_per_seat": 25.00,
  "toll_fee": 0.00,
  "instant_booking": true,
  "booking_mode": "INSTANT",
  "is_started": false,
  "is_completed": false,
  "is_cancelled": false,
  "vehicle_make": "Toyota",
  "vehicle_model": "Prius",
  "vehicle_color": "Silver",
  "notes": null,
  "created_at": "2026-07-27T10:00:00Z"
}
```

---

## 8. Bookings

### Booking Status Lifecycle

```
(instant trip)
  POST /bookings → status: PENDING_PAYMENT
  POST /payments/intent → Stripe client_secret
  [user pays via Stripe SDK]
  [Stripe webhook fires] → status: CONFIRMED
  [driver starts trip] → trip is_started: true
  [driver completes trip] → status: COMPLETED → payout triggered
  [10-min timer] → if still PENDING_PAYMENT, auto-cancelled

(non-instant trip)
  POST /bookings → status: PENDING
  [driver approves] → status: CONFIRMED
  [payment happens separately — see gap log]
```

**Critical:** If `booking.status === "PENDING_PAYMENT"`, show the payment screen. Do not show a "booking confirmed" screen yet. The booking expires in 10 minutes if payment is not completed.

### Create Booking
```
POST /bookings                   [Auth required]
```
```json
{ "trip_id": "uuid", "seats": 1 }
```
Returns: `BookingResponse`  
If `status === "PENDING_PAYMENT"` → immediately call `POST /payments/intent` next.

### My Bookings (as passenger)
```
GET /bookings/me                 [Auth required]
```

### Driver's Bookings
```
GET /bookings/driver             [Auth required]
GET /bookings/driver?status=PENDING
```
Status filter values: `PENDING | PENDING_PAYMENT | CONFIRMED | CANCELLED | COMPLETED | REJECTED`

### Trip Bookings (driver view)
```
GET /bookings/trip/{trip_id}     [Auth required]
GET /bookings/trip/{trip_id}?status=CONFIRMED
```

### Update Booking Status (driver approves/rejects)
```
PATCH /bookings/{booking_id}/status   [Auth required]
POST  /bookings/{booking_id}/status   [same, both work]
```
```json
{ "status": "CONFIRMED" }
```
Driver can set: `CONFIRMED` | `REJECTED` | `CANCELLED`

### Cancel Booking (passenger)
```
POST /bookings/{booking_id}/cancel    [Auth required]
```

### BookingResponse shape
```json
{
  "id": "uuid",
  "trip_id": "uuid",
  "passenger_id": "uuid",
  "seats": 1,
  "status": "PENDING_PAYMENT",
  "total_amount": 25.00,
  "created_at": "2026-07-27T10:00:00Z",
  "trip": { "id": "uuid", "origin_city": "Manchester", "destination_city": "London", "departure_time": "..." },
  "passenger": { "id": "uuid", "first_name": "James", "profile_photo_url": "..." }
}
```

---

## 9. Payments & Stripe

### Flow (instant booking)

```
1. POST /bookings → { status: "PENDING_PAYMENT", id: bookingId }
2. POST /payments/intent → { stripe_client_secret: "pi_xxx_secret_xxx", ... }
3. confirmPayment(stripe_client_secret) via Stripe SDK
4. Webhook fires server-side → booking flips to CONFIRMED
5. Poll GET /payments/{bookingId} or listen for push notification
```

### Create Payment Intent
```
POST /payments/intent            [Auth required]
```
```json
{ "booking_id": "uuid" }
```
Returns: `PaymentResponse` including `stripe_client_secret`.

### PaymentResponse shape
```json
{
  "id": "uuid",
  "booking_id": "uuid",
  "amount": 25.00,
  "platform_fee": 2.50,
  "payout_amount": 22.50,
  "status": "PENDING",
  "stripe_payment_intent_id": "pi_xxx",
  "stripe_client_secret": "pi_xxx_secret_xxx",
  "stripe_transfer_id": null,
  "created_at": "2026-07-27T10:00:00Z"
}
```

### Payment status values
| Status | Meaning |
|--------|---------|
| `PENDING` | Intent created, waiting for Stripe SDK |
| `SUCCEEDED` | Stripe confirmed payment, booking confirmed |
| `FAILED` | Payment failed |
| `REFUNDED` | Refund issued |
| `TRANSFERRED` | Payout sent to driver |

### Get Payment Status
```
GET /payments/{booking_id}       [Auth required]
```
Poll this (or use push notification) after Stripe SDK completes.

### Payment History
```
GET /payments/history?period=30d [Auth required]
```
`period` values: `7d | 30d | 6m | 1y`

### Stripe SDK — React Native (Expo)
```js
import { useStripe } from '@stripe/stripe-react-native';

const { confirmPayment } = useStripe();

// After POST /payments/intent returns client_secret:
const { error } = await confirmPayment(clientSecret, {
  paymentMethodType: 'Card',
  paymentMethodData: { billingDetails: { name: user.first_name + ' ' + user.last_name } },
});

if (error) {
  // show error.message to user
} else {
  // payment confirmed — poll GET /payments/{bookingId} or wait for push notification
}
```

### Stripe SDK — Flutter
```dart
await Stripe.instance.initPaymentSheet(
  paymentSheetParameters: SetupPaymentSheetParameters(
    paymentIntentClientSecret: clientSecret,
    merchantDisplayName: 'Rideway',
  ),
);
await Stripe.instance.presentPaymentSheet();
// on success → poll GET /payments/{bookingId}
```

---

## 10. Driver Payout (Stripe Connect)

Drivers must complete onboarding before payouts work. This is a one-time setup flow.

### Step 1 — Onboard
```
POST /payments/connect/onboard   [Auth required]
```
```json
{
  "first_name": "James",
  "last_name": "Harrison",
  "dob": { "day": 15, "month": 6, "year": 1990 },
  "address": { "line1": "12 Baker Street", "city": "London", "postal_code": "NW1 6XE" },
  "phone": "+447911123456",
  "account_holder_name": "James Harrison",
  "sort_code": "608371",
  "account_number": "12345678",
  "tos_accepted": true
}
```
Returns: `{ account_id, charges_enabled, payouts_enabled }`

### Step 2 — Upload ID document
```
POST /payments/connect/document?purpose=identity_document_front    [Auth required]
Content-Type: multipart/form-data
Field: file
```
`purpose` values: `identity_document_front` | `identity_document_back`  
Returns: `{ file_id: "file_xxx", message: "..." }`  
Call twice (front and back) for a driving licence.

### Step 3 — Attach document
```
POST /payments/connect/attach-document?front_file_id=file_xxx&back_file_id=file_yyy    [Auth required]
```
Returns: `{ "data": { "message": "Identity document attached successfully" } }`

### Check Connect Status
```
GET /payments/connect/status     [Auth required]
```
```json
{ "connected": true, "charges_enabled": true, "payouts_enabled": true, "account_id": "acct_xxx" }
```
Use this to gate the "Enable Payouts" flow — show onboarding only if `connected === false`.

### Driver Balance
```
GET /payments/connect/balance    [Auth required]
```
```json
{ "available": 22.50, "pending": 0.00, "currency": "gbp" }
```

### Request Manual Payout
```
POST /payments/connect/request-payout    [Auth required]
```
Triggers payout of all available balance to the driver's bank account.

### Driver Payout History
```
GET /payments/connect/payout-history     [Auth required]
```

---

## 11. Notifications & Devices

### Register Device (for push notifications)
```
POST /notifications/devices/register    [Auth required]
```
```json
{
  "device_token": "ExponentPushToken[xxx]",
  "platform": "ios",
  "device_name": "iPhone 15",
  "app_version": "1.0.0"
}
```
Call on login and on app startup. `platform` values: `ios | android`

### Update Device Token (when FCM/APNS rotates token)
```
POST /devices/update-token       [Auth required]
```
```json
{
  "old_device_token": "old_token",
  "new_device_token": "new_token",
  "platform": "android",
  "device_name": "Pixel 8",
  "app_version": "1.0.0"
}
```

### List Notifications
```
GET /notifications?limit=50&offset=0    [Auth required]
```

### Mark Notification Read
```
POST /notifications/{notification_id}/read    [Auth required]
```

### Notification types (for UI icons/copy)
| type | Trigger |
|------|---------|
| `BOOKING_REQUEST` | New booking / payment complete / seat held |
| `BOOKING_CANCELLED` | Booking cancelled or rejected |
| `TRIP_STARTED` | Driver started the trip |
| `TRIP_COMPLETED` | Trip finished |
| `PAYMENT_RECEIVED` | Driver receives payout |
| `REVIEW_RECEIVED` | Someone left you a review |

---

## 12. Messaging

Per-booking chat between passenger and driver.

### List Messages
```
GET /messages/{booking_id}       [Auth required]
```
Only the passenger or the driver of that booking can read messages.

### Send Message
```
POST /messages/{booking_id}      [Auth required]
```
```json
{ "content": "Hi, I'm on my way to the pickup point." }
```

### MessageResponse shape
```json
{
  "id": "uuid",
  "booking_id": "uuid",
  "sender_id": "uuid",
  "content": "Hi, I'm on my way.",
  "created_at": "2026-07-27T10:05:00Z"
}
```

---

## 13. Reviews

### Create Review
```
POST /reviews                    [Auth required]
```
```json
{
  "trip_id": "uuid",
  "reviewee_id": "uuid",
  "rating": 5,
  "comment": "Great driver, smooth ride."
}
```
One review per (reviewer, trip) pair. Call after `booking.status === "COMPLETED"`.

### Get User Reviews
```
GET /reviews/user/{user_id}
```
No auth required.

### ReviewResponse shape
```json
{
  "id": "uuid",
  "trip_id": "uuid",
  "reviewer_id": "uuid",
  "reviewee_id": "uuid",
  "rating": 5,
  "comment": "Great driver!",
  "created_at": "2026-07-27T12:00:00Z"
}
```

---

## 14. Support Tickets

### Raise Ticket
```
POST /tickets                    [Auth required]
```
```json
{
  "category": "TRIP_ISSUE",
  "subject": "Driver was late",
  "description": "The driver arrived 20 minutes after the agreed pickup time.",
  "reported_user_id": "uuid-optional",
  "trip_id": "uuid-optional"
}
```

### My Tickets
```
GET /tickets/me                  [Auth required]
```

### Get Ticket
```
GET /tickets/{ticket_id}         [Auth required]
```

### TicketResponse shape
```json
{
  "id": "uuid",
  "reporter_id": "uuid",
  "category": "TRIP_ISSUE",
  "subject": "Driver was late",
  "description": "...",
  "status": "OPEN",
  "admin_note": null,
  "reported_user_id": null,
  "trip_id": null,
  "created_at": "2026-07-27T10:00:00Z"
}
```
`status` values: `OPEN | IN_REVIEW | RESOLVED | CLOSED`

---

## 15. Misc (Promos, Playlist, Referral)

### Promos List
```
GET /users/promos
```
Returns: `{ items: [{ title, description, promo_type, code }] }`

### Student Promo
```
GET /users/promos/student
```

### Referral URL
```
GET /users/me/referral           [Auth required]
```
Returns: `{ url: "https://rideway.co.uk/refer?code=xxx" }`

### Playlist
```
GET /users/playlist
```
Returns: `{ url: "https://..." }` — link to a Spotify/YouTube playlist for trips.

---

## 16. Admin Dashboard

All admin endpoints are under `/admin/*` and require the caller's account to have `is_admin: true`. Any non-admin call returns `403 Admin privileges required`.

**How to detect admin role:** `is_admin` is NOT currently in `UserPrivateResponse`. The only way to know if the logged-in user is an admin is to call `GET /admin/metrics` — if it returns 200 they are an admin; if 403 they are not. See Gap Log item for the missing `is_admin` field.

### Overview / Dashboard Metrics
```
GET /admin/metrics               [Admin required]
```
Returns `AdminMetricsResponse`:
```json
{
  "total_users": 142,
  "total_trips": 38,
  "confirmed_bookings": 91,
  "total_revenue": 2250.00,
  "platform_fee_total": 225.00,
  "trips_created_last_7_days": 12,
  "booking_conversion_rate": 0.74,
  "trip_completion_rate": 0.88,
  "repeat_users": 34
}
```
- `booking_conversion_rate` — confirmed bookings / total bookings (0–1)
- `trip_completion_rate` — completed bookings / confirmed bookings (0–1)
- `platform_fee_total` — Rideway's cut across all payments

### User Management
```
GET /admin/users?limit=50&offset=0    [Admin required]
```
Returns `list[UserPrivateResponse]` — full private profiles for all users.  
No search/filter yet (see Gap Log). Paginate with `limit` / `offset`.

```
POST /admin/users/{user_id}/verify-email    [Admin required]
```
Force-sets `is_email_verified: true`. No body. Returns updated `UserPrivateResponse`.

### KYC / Identity Verification

```
POST /admin/users/{user_id}/verification/approve    [Admin required]
```
No body. Sets user's `identity_verification_status` to `APPROVED`. Sends approval email. Returns updated `UserPrivateResponse`.

```
POST /admin/users/{user_id}/verification/reject     [Admin required]
```
```json
{ "reason": "The licence image is blurry. Please resubmit a clear, well-lit photo." }
```
`reason` is optional. Sets status to `REJECTED`. Returns updated `UserPrivateResponse`.

**`identity_verification_status` values:** `PENDING | APPROVED | REJECTED`

To build the KYC queue: call `GET /admin/users` then filter client-side for `identity_verification_status === "PENDING"`. (A dedicated pending-queue endpoint does not exist yet — see Gap Log.)

### Trip Management
```
GET /admin/trips?limit=50&offset=0    [Admin required]
```
Returns `list[TripResponse]` — all trips across all drivers, with full driver detail embedded.

### Booking Management & Disputes
```
GET /admin/bookings?limit=50&offset=0    [Admin required]
```
Returns `list[BookingResponse]` — all bookings platform-wide with trip and passenger detail.

```
POST /admin/bookings/{booking_id}/resolve    [Admin required]
```
```json
{ "status": "COMPLETED" }
```
Resolves a dispute. Only `COMPLETED` or `CANCELLED` are valid. Returns updated `BookingResponse`.

### Support Tickets (Admin View)
```
GET /tickets/admin/all                    [Admin required]
GET /tickets/admin/all?status=OPEN
```
Returns all tickets platform-wide. Filter by `status`: `OPEN | IN_REVIEW | RESOLVED | CLOSED`.

```
PATCH /tickets/admin/{ticket_id}          [Admin required]
```
```json
{ "status": "RESOLVED", "admin_note": "Refund issued. Booking cancelled." }
```
Update a ticket status and add an admin note.

### Admin Endpoint Summary

| Endpoint | What it powers |
|----------|---------------|
| `GET /admin/metrics` | Overview page — KPI tiles |
| `GET /admin/users` | User list page (paginated, filter client-side) |
| `POST /admin/users/{id}/verify-email` | Force-verify email in user detail |
| `POST /admin/users/{id}/verification/approve` | KYC approve action |
| `POST /admin/users/{id}/verification/reject` | KYC reject action |
| `GET /admin/trips` | Trips management page |
| `GET /admin/bookings` | Bookings management page |
| `POST /admin/bookings/{id}/resolve` | Dispute resolution action |
| `GET /tickets/admin/all` | Support ticket queue |
| `PATCH /tickets/admin/{id}` | Update ticket status / add note |

---

## 17. Error Reference  

| HTTP | detail | Cause |
|------|--------|-------|
| 400 | "Email already registered" | Duplicate registration |
| 400 | "Invalid credentials" | Wrong email/password |
| 400 | "Invalid or expired OTP" | OTP wrong / timed out |
| 400 | "Trip already departed" | Booking after departure |
| 400 | "Not enough seats available" | Race condition on last seat |
| 400 | "Driver cannot book own trip" | Driver trying to book their trip |
| 400 | "Can only reject pending bookings" | Wrong booking state |
| 400 | "You must accept the Terms of Service" | `tos_accepted: false` |
| 401 | "User not found" | Expired or invalid token |
| 403 | "Not allowed to cancel booking" | Actor is neither driver nor passenger |
| 404 | "Trip not found" | Bad trip_id |
| 404 | "Booking not found" | Bad booking_id |
| 422 | Validation error object | Missing or wrong-type fields |
| 429 | Rate limit hit | Too many requests |
| 500 | "Payment processing error" | Stripe API error — retry once |

**Rate limits** (per user, per minute):
- Auth register: 5
- Auth login: 10
- Resend OTP: 3
- Create booking: 10
- Create payment intent: 5
- Connect onboard: 3

---

## 18. Gap Log — Designs Without API

Entries marked **✅ EXISTS** were previously thought missing but are confirmed live. Entries marked **⚠ GAP** still need backend work before the screen can go live.

### App (non-admin) gaps

| Screen / Feature | Status | Notes |
|-----------------|--------|-------|
| **Non-instant booking payment** | ⚠ GAP | No payment flow for `PENDING` bookings. Only `PENDING_PAYMENT` (instant) bookings have a payment intent. Non-instant bookings require driver approval first; the payment step after approval is not built yet. |
| **Refund / cancellation policy** | ⚠ GAP | No `POST /payments/{id}/refund` endpoint. Cancelling a booking after payment has no automated refund route. |
| **In-app notification badge count** | ⚠ GAP | `GET /notifications` returns the full list but no unread-count endpoint. Count `is_read === false` client-side. |
| **Mark all notifications read** | ⚠ GAP | No bulk `POST /notifications/read-all`. Only individual mark-read exists. |
| **Trip waypoints / stops** | ⚠ GAP | `TripCreate` has no `waypoints` or `stops` field. If design shows intermediate stops this needs a backend schema change. |
| **Favourite trips / saved searches** | ⚠ GAP | No `/users/me/favourites` or saved-search endpoint. |
| **Promo code redemption** | ⚠ GAP | `GET /users/promos` lists promos but no `POST /bookings/{id}/apply-promo` or discount logic. Promo codes are display-only. |
| **Trip sharing (deep link)** | ⚠ GAP | No `GET /trips/{id}/share-link`. Can deep-link using trip ID directly if the app handles URL routing. |
| **Driver vehicle photo on trip card** | ⚠ GAP | `POST /users/me/vehicle/photo` uploads to the user profile but `TripResponse` does not include a `vehicle_photo_url`. |
| **Live location / tracking** | ⚠ GAP | No WebSocket or location-ping endpoint. Tracking screen in the design has no backend equivalent yet. |
| **Verified driver badge on public profile** | ⚠ GAP | `identity_verification_status` is on `UserPrivateResponse` (own profile only). `UserPublicResponse` (other users' profiles) does not expose it. Passenger cannot see if a driver is KYC-approved from the trip card. |

### Admin dashboard gaps

| Page / Feature | Status | Notes |
|----------------|--------|-------|
| **Overview metrics** | ✅ EXISTS | `GET /admin/metrics` — total users, trips, revenue, fees, conversion rate, completion rate, repeat users. Wire this up, remove mock data. |
| **User list** | ✅ EXISTS | `GET /admin/users?limit=50&offset=0` — full paginated list with private fields. No server-side search/filter yet (filter client-side for now). |
| **Trip management** | ✅ EXISTS | `GET /admin/trips?limit=50&offset=0` — all trips with driver detail. |
| **Booking management + dispute resolve** | ✅ EXISTS | `GET /admin/bookings` + `POST /admin/bookings/{id}/resolve` with `{ status: "COMPLETED" \| "CANCELLED" }`. |
| **KYC / Verification queue** | ✅ EXISTS (partial) | `POST /admin/users/{id}/verification/approve` and `/reject` exist. No dedicated pending-queue endpoint — filter `GET /admin/users` client-side for `identity_verification_status === "PENDING"`. |
| **Support ticket queue** | ✅ EXISTS | `GET /tickets/admin/all?status=OPEN` + `PATCH /tickets/admin/{id}` with `{ status, admin_note }`. These are under `/tickets/`, not `/admin/`, but they are admin-gated. |
| **Finance / platform payments** | ⚠ GAP | No endpoint to list all payments platform-wide. Revenue totals are available via `/admin/metrics` only. |
| **Admin role detection on login** | ⚠ GAP | `is_admin` field is NOT returned in `UserPrivateResponse` / `AuthTokenResponse`. The only way to detect admin is to call `GET /admin/metrics` and check for 200 vs 403. Backend needs to add `is_admin: bool` to `UserPrivateResponse`. |
| **Admin user search / filter** | ⚠ GAP | `GET /admin/users` returns all users but has no `?search=`, `?role=`, or `?verification_status=` query param. Filtering must happen client-side for now. |
| **Pending-verification queue endpoint** | ⚠ GAP | Repo has `list_pending_verifications()` but it is not wired to any route. Would need `GET /admin/users/pending-verification` to avoid loading all users just to filter. |
