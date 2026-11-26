# PocketPilot Android Companion — design (not implemented)

**Status: nothing in this folder runs yet.** This is the plan for the small Android app that
detects UPI payment notifications and sends them to PocketPilot for review. The backend side
is already built and tested.

## Why a separate app?

A website cannot read notifications from other apps. Android allows it only through a
`NotificationListenerService`, which the user must switch on manually in
*Settings → Apps → Special app access → Notification access*.

## How it will work

```
UPI app notification
   │  (Android delivers it to our NotificationListenerService)
   ▼
1. Package allow-list check ── not PhonePe/GPay/Paytm/BHIM? → ignore
2. Parse on the phone        ── not a successful debit?   → ignore
3. Build payload (parsed fields only, never the full text)
4. Save to a local queue (Room) → WorkManager uploads when online
   ▼
POST /api/pending-transactions   (Bearer token)
   ▼
PocketPilot shows it as "Awaiting review" → user taps Add / Edit / Reject
```

Nothing is added to the budget automatically. The user always decides.

## Planned modules (Kotlin)

| Part | Responsibility |
|---|---|
| `LoginActivity` | Log in with the PocketPilot account (`POST /api/auth/login`); store the token in `EncryptedSharedPreferences` |
| `PermissionScreen` | Explain why notification access is needed; open the system settings page; show current status |
| `UpiNotificationListener` (`NotificationListenerService`) | Receive notifications, filter by package, hand matches to the parser |
| `UpiParser` | Kotlin port of `backend/app/utils/upi_parser.py` (same rules, same test cases) |
| `PendingQueue` (Room) | Store detected payments so none are lost while offline |
| `UploadWorker` (WorkManager) | Send queued items with retry and back-off; delete them after a 201 or 200 response |
| `SettingsScreen` | Pause detection, choose which apps to watch, log out |

Package allow-list (to confirm on real devices): `com.phonepe.app`,
`com.google.android.apps.nbu.paisa.user` (Google Pay), `net.one97.paytm`, `in.org.npci.upiapp` (BHIM).

## Backend contract (implemented)

```json
POST /api/pending-transactions
Authorization: Bearer <token>
{
  "amount_paise": 50000,
  "source_app": "phonepe",               // phonepe | gpay | paytm | bhim | other
  "counterparty": "Campus Cafe",         // optional
  "transaction_ref": "432112345678",     // optional, 6–32 letters/digits
  "notification_hash": "<64 hex chars>", // SHA-256 of package|title|text|postTime (UTC ISO)
  "detected_at": "2026-11-03T13:45:00+05:30"
}
```

- Send at least one of `transaction_ref` or `notification_hash`.
- `201` means a new pending transaction. `200` with `"duplicate": true` means it was already received. Treat both as success, so retries are always safe.
- `401` means the token expired: ask the user to log in again, and keep the queue.
- `422` means invalid data: drop the item and log it locally.
- Duplicates are detected by reference or hash, never by amount + date.

## Parsing rules (mirror the backend exactly)

- Only **successful debits**: text contains paid / sent / debited / "payment successful".
- Ignore anything mentioning received, credited, request, collect, failed, declined, pending,
  reversed, refund, cashback, reward, expired, cancelled, due or reminder.
- Amount: `₹`, `Rs`, `Rs.` or `INR` followed by digits, e.g. `₹1,250.50` → 125050 paise.
- Recipient: the text after the first "to …", up to "on / via / using / from / UPI / Ref" or punctuation.
- Reference: 10–16 digits after ref / UTR / txn / "transaction ID".

The same example notifications in `backend/tests/test_upi_parser.py` should become Kotlin unit
tests, so both parsers always agree. Real notification wording varies by app version and
language, so the rules must be checked against real notifications before release.

## Privacy and safety

- Only allow-listed apps are processed. All other notifications are ignored on the phone.
- The full notification text never leaves the phone, only the parsed fields above.
- No balances, account numbers or other notifications are read or stored.
- The user can pause detection in the app, or revoke access in Android settings at any time.
- The token is stored encrypted, and logging out clears it and the queue.
- There is no public API for reading full PhonePe / Google Pay / Paytm history, and this design doesn't rely on one.

## Test plan

1. Parser unit tests (shared cases with the backend).
2. Instrumented test that posts fake notifications to the listener.
3. Manual tests on real devices with each UPI app: success, failed, request, credit, refund.
4. Offline test: airplane mode → make payments → reconnect → each appears exactly once.
5. Run `backend/scripts/smoke_test.py` against the same server.
