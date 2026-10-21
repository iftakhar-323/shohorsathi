# ShohorSathi Demonstration Guide

Step-by-step walkthrough to present the entire ShohorSathi platform on a single laptop in approximately 15 minutes.

---

## 1. Starting with Demo Data

Complete installation instructions from a clean clone are detailed in [SETUP.md](SETUP.md).

### Quick Start:

```bash
# Option A: Zero-Docker Mode (instant, lightweight, no Docker needed):
python scripts/standalone_server.py
# (in another terminal):
pnpm install && pnpm dev

# Option B: Full Docker Mode:
scripts/up.sh --demo
# (in another terminal):
pnpm install && pnpm dev
```

To reset the database to a clean demo state prior to a formal demonstration:
`docker compose down -v && scripts/up.sh --demo` (or restart `python scripts/standalone_server.py`).

| Application | URL | Demo Account (Password: `demo1234` for all) |
|---|---|---|
| **Customer Site** | http://localhost:5173 | Dhaka: `01711000001` (Rahim - tenant, Dhanmondi) · `01711000002` (Nusrat) · `01711000003` (Tanvir)<br>Khulna: `01711000004` (Farhana) · `01711000005` (Arif) · `01711000006` (Sumaiya) |
| **Provider Portal** | http://localhost:5174 | Dhaka: `01811000001` (Karim - Electrician) · `01811000002` (Salma - Cleaner) · `01811000003` (Jamal - AC)<br>Khulna: `01811000004` (Masud) · `01811000005` (Rehana) · `01811000006` (Saiful) |
| **Admin Panel** | http://localhost:5175 | `01700000000` (Super Admin) |

---

## 2. Recommended Presentation Walkthrough

### 1. Customer Home Experience (Guest View)
- Displays bilingual toggle in header (Bangla / English switch).
- Hero section with live search and Bengali voice recognition button (`bn-BD`).
- Seasonal campaign banners with imagery (e.g., Eid deep cleaning, Monsoon waterproofing, Summer AC tune-up).
- Neighbourhood group deals section with real-time participation status and target lock-in progress.
- 1-click Emergency service assistance drawer.

### 2. Service Booking Flow
- Navigate to **Services → AC Cleaning → Book**:
  - Select service date, time slot, and attach problem photos.
  - Optional toggle: **"Female Provider Preferred"** (dispatched exclusively to verified female technicians).
- Add to cart → Checkout:
  - Payment choices: Cash on delivery, bKash / Nagad direct payments, loyalty reward points redemption.
  - Tenant / Landlord mode toggle: allows entering landlord's phone number for repair expense approval.

### 3. Customer Dashboard & Safety (Sign in as Rahim: `01711000001`)
- **My Orders:**
  - Completed order view: service timeline, photo evidence before/after, 5-star customer review, warranty certificate.
  - Upcoming booking view: secure 4-digit arrival verification code, live family tracking shareable URL, SOS emergency button.

### 4. AI Photo Quote & Diagnostic Analysis (`/ai-quote`)
- Interactive sample problem selector: Click on sample images (AC water leakage, pipe burst, burnt electrical wall outlet).
- Claude Vision AI analyzes the visual damage or text description:
  - Identifies the specific root cause and severity level (Low / Medium / High / Critical).
  - Provides estimated price range in BDT and recommended catalog service.
  - 1-click "Book Recommended Service" button for instant resolution.

### 5. Digital Home Profile & Health Meter (`/home-profile`)
- Displays overall Home Health Score (e.g., 88/100) based on age of electrical wiring, plumbing, and appliances.
- Upcoming maintenance reminders (e.g., AC filter cleaning, water purifier filter change).
- Tenant & Landlord mode: displays pre-authorized repair cost limits and landlord contact details.
- Landlord-approved orders automatically generate an official printable **Rent Deduction Voucher**.

### 6. Multi-City Expansion (Khulna & Chattogram)
- Switch city to **Khulna** via the header city selector:
  - 15 real urban coverage areas: Sonadanga, Khalishpur, Daulatpur, Boyra, Gollamari, Nirala, Shibbari, Dakbangla, Moylapota, Tutpara, Labanchara, Rupsha, Khan Jahan Ali, Fulbari Gate, Rayermahal.
  - **City Issues:** 16 verified photo reports across 8 categories (waste management, streetlight failure, waterlogging, damaged roads, open drains, mosquito breeding, water supply disruptions).
  - Forwarded to specific municipal authorities (KCC Conservancy, KCC Engineering, KCC Health, Khulna WASA, WZPDCL).
  - Public **Transparency Dashboard** showing median resolution turnaround times, resolution rates, and zero personal data exposure.

### 7. Provider Portal Experience (Sign in as Karim: `01811000001`)
- **Job Inbox:** Displays available, in-progress, and past jobs.
- **Two-Way Rating:** Providers can rate customers after job completion.
- **Earnings & Instant Payout:** View accumulated earnings and request instant disbursement to bKash wallet.
- **Training & Badges:** Interactive safety training modules with quiz verification, issuing digital completion certificates and profile verification badges.
- **Micro-Insurance:** Micro-insurance policy enrollment and claim filing for on-duty health or accident protection.

### 8. Admin Control Center (Sign in as Admin: `01700000000`)
- Executive platform dashboard: real-time GMV, order completion rates, and provider capacity.
- **City Issues Management:** Forward citizen reports to relevant civic agencies, download CSV feeds, and review resolution photos.
- **Group Deals & Promotions:** Create neighbourhood group deals, schedule seasonal discount packages, and manage sponsored service placements.
- **Analytics & Machine Learning Insights:**
  - 7-day demand forecasting model per service category.
  - Churn prediction identifying at-risk customers with 1-click win-back campaign triggers.
  - Fraud detection signals (burst bookings, address clustering, unusual cancellation patterns).

---

## 3. Important Presentation Notes

- **Synthetic Analytics History:** Analytics metrics for forecasting, customer churn, and fraud signals include an 8-week synthetic historical baseline (customer IDs `#9000+`) generated by `scripts/demo_analytics_history.py` to ensure visual clarity during evaluations.
- **Payment & Messaging Simulation:** Payments run against a mock gateway; SMS and WhatsApp notifications are cleanly logged to the development console.
- **Automated Browser Tour Test:** Run `cd apps/e2e && npx playwright test tests/demo-tour.spec.ts` to automatically navigate every screen across all three applications and capture full-page verification screenshots in `apps/e2e/test-results/tour/`.
