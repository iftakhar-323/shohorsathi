# Compliance notes (Bangladesh)

How ShohorSathi is built to fit the rules that apply to it, and what still needs a lawyer's confirmation before launch.
This is an engineering summary, not legal advice.

## 1. ShohorSathi Credit is not e-money

Bangladesh Bank's (draft) e-money regulation requires a PSP licence to hold customer money that is redeemable for
cash, with a minimum penalty of Tk 50 lakh for operating without one. ShohorSathi therefore has **no cash wallet**:

- there is no top-up: credit cannot be bought with money (the top-up endpoint and payment purpose were removed);
- credit only comes from refunds, referral bonuses, promotions and admin goodwill adjustments;
- it can only be spent on ShohorSathi orders, and cannot be withdrawn or sent to another person;
- every movement is in an append-only ledger (`services/loyalty`, `Entry`).

**Confirm with counsel:** that closed-loop store credit of this kind falls outside the e-money definition.

## 2. Advance payments and escrow

Digital Commerce Operation Guidelines 2021 (with Bangladesh Bank's 30 June 2021 circular): if goods are not handed
over within 72 hours, at most 10% may be taken in advance, unless the money sits in a Bangladesh Bank-approved escrow;
payment gateways hold advance payments and pay the merchant after delivery is proven.

- Online payments are made through the payment gateway (SSLCommerz / bKash / Nagad), which holds the funds; the
  payment service's ledger records them as *held* until the order or custom job is completed, then *released*;
  cancellations are refunded automatically (`services/payment`).
- Custom-request advances default to **10%** (`CUSTOM_REQUEST_ADVANCE_PERCENT`).
- Product orders not delivered within `ORDER_DELIVERY_DEADLINE_DAYS` (default 5) are flagged on the admin dashboard
  and in the order list (`?overdue=1`) so they are delivered or cancelled and refunded.

**Confirm with counsel and the gateway:** the guidelines' current version; that the gateway's settlement holding
counts as the required escrow for our merchant account; whether service bookings (not goods) fall under the same caps.

## 3. Personal Data Protection Ordinance 2025

| Duty | Implementation |
|---|---|
| Consent, specific and recorded | Sign-up requires accepting the terms and privacy notice; the version and time are stored (`User.terms_version`, `terms_accepted_at`). Promotional messages are a separate opt-in (`marketing_opt_in`). |
| Notice | `/privacy` and `/terms` in Bangla and English (`packages/web-core/src/content/legal.ts`, marked draft). |
| Minimisation and retention | Rejected provider applicants' NID and photos are deleted after `REJECTED_DOCUMENT_RETENTION_DAYS` (90). Providers see customer contact details only after taking a job. |
| Security of sensitive data | NID and ID-card images are encrypted at rest (Fernet, `MEDIA_ENCRYPTION_KEY`), viewable only by the owner and admins, and every opening is logged (`MediaAccess`). |
| Access / portability | Profile → "Download all my data" gathers the user's records from every service (`/api/me/export/`). |
| Erasure | Profile → "Delete my account" (password confirmed). Auth anonymises the account and publishes `user.deleted`; each service removes or redacts its copy. Order and payment amounts stay without identity for accounting. |
| Breach notification | See the incident steps in `docs/deploy.md`; the regulator and affected users must be told promptly. |
| Localisation | Host the servers and backups in Bangladesh, or confirm which data classes may leave the country. |

**Confirm with counsel:** the gazetted text and effective dates (some sections start 18 months after gazette);
whether NID images are "sensitive" or "restricted" data and the resulting storage location rules; the retention
period for rejected applicants and for accounting records.
