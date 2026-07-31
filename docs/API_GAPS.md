# API Gaps & Status Tracker

Last updated: 2026-07-30

---

## ✅ Fixed this session (2026-07-30)

| Item | Fix |
|---|---|
| `POST /notifications/devices/register` returning 500 | `DevicePlatform` enum `values_callable` fix — SQLAlchemy was sending `ANDROID` (NAME) but DB stored `android` (VALUE) |
| `POST /reviews` returning 500 | `ReviewResponse` UUID fields were `str` — Pydantic v2 raised `ValidationError` not caught by `except ValueError` |
| `trips_completed` always 0 after completing ride | `complete_trip()` bypassed `_handle_completion()` — fixed to increment counter for driver + all passengers |
| Google sign-in showing email verification prompt | Backend was correct (sets `is_email_verified=True` on Google auth). **Frontend issue** — Glory's Flutter nav guard was checking stale local flag, not the API response |
| `POST /auth/register` 500 on `@example.com` emails | Email delivery failure was crashing registration. Wrapped in try/except — registration succeeds regardless of email deliverability |
| `is_new_user` not in auth response | Added `is_new_user: bool` to `user` object on all auth endpoints — `register=true`, `login=false`, Google dynamic |
| Driver could post ride without identity verification | Added identity check in `create_trip()` — currently **commented out** for QA testing, uncomment before production |
| No duplicate review prevention | Added `get_by_trip_and_reviewer` guard — returns 400 if same user reviews same trip twice |
| No refund on booking cancellation | Full 100% Stripe refund now fires automatically on `PATCH /bookings/{id}/status → CANCELLED` |
| Stripe webhook processed inline (fragile) | Webhook now validates signature inline → returns 200 immediately → enqueues Celery task with 5-retry exponential backoff + DLQ |
| `POST /notifications/send` missing | New endpoint — accepts `recipient_id`, `title`, `body`, `type`, `data{trip_id, other_user_id, booking_id, route_summary}`. Backend auto-fills `other_user_name` and `route_summary` from IDs |
| FCM push not reaching Android consistently | Switched to data-only FCM messages — `title`, `body`, `type` and all IDs now inside `message.data`. Flutter's `onMessage` fires in all app states |
| `type` field in `/notifications/send` always `GENERAL` | Pydantic reserved word conflict — fixed with `Field(alias="type")` so Glory sends `"type"` and it maps correctly |
| Notification deep linking missing context | `data` column added to notifications table. All notifications (push + in-app) carry `type`, `other_user_name`, `route_summary`, `trip_id`, `booking_id` |
| New notification types missing | Added `CHAT`, `PAYMENT`, `BOOKING`, `GENERAL` to `NotificationType` enum (migrations 0010, 0011) |
| `route_summary` not passable directly | Glory can now pass `route_summary` in `data` directly for chat screens where `trip_id` is unavailable |

---

## 🐛 Remaining Bugs

### Error response envelope inconsistency
Doc (`frontend-handover.md §1`) shows `{ "detail": "message" }` but live API returns `{ "data": null, "error": "message" }`.
**Fix needed:** Update `frontend-handover.md` to match actual API shape — the API behaviour is correct, the doc was wrong.
**Owner:** Backend (doc update only)

---

## 🔧 Missing Fields on Existing Endpoints

### `is_admin` not in `UserPrivateResponse`
No way to gate admin UI after login without probing an admin endpoint.
**Fix:** Add `is_admin: bool` to `UserPrivateResponse`.

### `TicketResponse` missing priority and reporter detail
Admin ticket queue shows bare `reporter_id` UUID with no name/email. No priority field.
**Fix:** Embed `reporter: { id, first_name, last_name, email }` and add `priority: LOW | MEDIUM | HIGH` to `TicketResponse`.

### `BookingResponse` missing dispute fields
No `is_disputed: bool` or `dispute_reason: str | null` on bookings.
**Fix:** Add fields; have ticket creation optionally set `is_disputed = true` on the linked booking.

---

## 🆕 New Endpoints Needed

### Admin — user search/filter
```
GET /admin/users?search=<name|email>&role=DRIVER|PASSENGER&verification_status=PENDING|APPROVED|REJECTED&limit=50&offset=0
```
Without this the admin Users page has to load everyone and filter client-side.

### Admin — pending verification queue
`list_pending_verifications()` already exists in the repo but is not wired to a route.
```
GET /admin/users/pending-verification?limit=50&offset=0
```

### Admin — platform-wide payments list
```
GET /admin/payments?limit=50&offset=0&status=SUCCEEDED|FAILED|REFUNDED
```
Returns per-payment records platform-wide. The admin Finance page has no data source without this.

### Admin — time-series metrics
```
GET /admin/metrics/bookings-timeseries?days=7
GET /admin/metrics/revenue-timeseries?weeks=5
```
Returns `[{ "date": "2026-07-21", "value": 1830 }, ...]`. Needed for admin dashboard charts.

### Admin — activity feed
```
GET /admin/activity?limit=20
```
Chronological platform events (signups, bookings, verifications, payments). Needed for admin overview.

### Web OAuth for Google sign-in
Only `POST /auth/google/mobile` exists (native `id_token`). Web frontend needs either:
- Standard redirect flow: `GET /auth/google/authorize` → redirect → `GET /auth/google/callback`
- Or confirmation that the mobile endpoint accepts tokens from Google's web JS SDK

---

## ⚠️ Frontend-Only Issues (no backend change needed)

| Issue | Root Cause |
|---|---|
| Google sign-in showing email verification screen | Flutter nav guard checking stale local flag — read `user.is_email_verified` from API response instead |
| `type: GENERAL` always showing | Flutter was sending `notification_type` (old field name) — change to `type` in request body |
| `route_summary` missing in push | Flutter not passing `data.route_summary` or `data.trip_id` — both are optional, pass whichever is available |
| `changePassword` Dart compile error | `changePassword` method missing from `AuthRepo` class in Flutter |
