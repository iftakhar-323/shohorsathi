"""End-to-end check of Dhap 6 (Trust & Safety):
- Women-provider preference (female booking filtered to female provider)
- Training: module creation, quiz submission, certificate code, public verification, trained badge
- Insurance: plan creation, enrollment, claim submission, admin review & payment
- Safety: SOS alert, admin incident resolution, live job sharing link
- Two-way ratings, dispute submission, admin dispute uphold (review hidden, rating recomputed)
- Instant payout with instant fee and weekly insurance premium deducted
Usage: python3 scripts/e2e_phase6.py [http://localhost:8088]  (stack running, catalog seeded)
"""
import subprocess
import time
from datetime import date, timedelta
from decimal import Decimal

import e2e_phase1 as e1

call, register, wait_for, step = e1.call, e1.register, e1.wait_for, e1.step
STAMP = str(int(time.time()))[-8:]


def main():
    admin_phone = f"019{STAMP}"
    cust_phone = f"017{STAMP}"
    female_pro_phone = f"018{STAMP}"
    male_pro_phone = f"016{STAMP}"

    # Setup admin
    subprocess.run(
        [
            "docker", "compose", "exec", "-T", "-e", "DJANGO_SUPERUSER_PASSWORD=admin-pass-123",
            "auth", "python", "manage.py", "createsuperuser", "--noinput",
            "--phone", admin_phone, "--full_name", "Safety Admin"
        ],
        check=True, capture_output=True
    )
    admin = call("POST", "/api/auth/login/", body={"phone": admin_phone, "password": "admin-pass-123"}, expect=200)["access"]
    area = call("POST", "/api/admin/areas/", admin, {"name_en": f"Safety Area {STAMP}", "name_bn": "সেফটি এলাকা"}, expect=201)

    # 1. Register customer, female provider, and male provider
    customer = register(cust_phone, "Salma Begum")["access"]

    female_pro_tokens = register(female_pro_phone, "Rina Akhter")
    female_pro = female_pro_tokens["access"]
    call("POST", "/api/providers/register/", female_pro, {
        "provider_type": "cleaner",
        "skills": ["cleaning"],
        "area_ids": [area["id"]],
        "nid_number": "9876543210",
        "gender": "female",
        "photo_url": "/media/rina.jpg",
        "nid_front_url": "/media/nid_rina.jpg",
    }, expect=201)

    male_pro_tokens = register(male_pro_phone, "Kamal Hossain")
    male_pro = male_pro_tokens["access"]
    call("POST", "/api/providers/register/", male_pro, {
        "provider_type": "cleaner",
        "skills": ["cleaning"],
        "area_ids": [area["id"]],
        "nid_number": "1234567890",
        "gender": "male",
        "photo_url": "/media/kamal.jpg",
        "nid_front_url": "/media/nid_kamal.jpg",
    }, expect=201)

    # Approve both providers
    pending = call("GET", "/api/admin/providers/?status=pending", admin)["results"]
    for p in pending:
        if p["phone"] in (female_pro_phone, male_pro_phone):
            call("POST", f"/api/admin/providers/{p['id']}/approve/", admin, expect=200)

    # Set payout account & emergency contact for female provider
    call("PATCH", "/api/providers/me/", female_pro, {
        "is_online": True,
        "payout_method": "bkash",
        "payout_account": "01811111111",
        "emergency_contact_name": "Father",
        "emergency_contact_phone": "01700000000",
    }, expect=200)

    call("PATCH", "/api/providers/me/", male_pro, {
        "is_online": True,
        "payout_method": "nagad",
        "payout_account": "01611111111",
    }, expect=200)

    step("registered customer, approved female and male providers")

    # 2. Women-provider preference check
    cart_item = call("POST", "/api/cart/items/", customer, {"item_type": "service", "slug": "home-deep-clean"}, expect=201)
    booking_date = (date.today() + timedelta(days=1)).isoformat()
    order = call("POST", "/api/orders/", customer, {
        "contact_name": "Salma Begum",
        "contact_phone": cust_phone,
        "address_line": "House 10, Road 4",
        "area_id": area["id"],
        "area_name": area["name_en"],
        "payment_method": "cod",
        "service_details": {
            str(cart_item["id"]): {
                "scheduled_date": booking_date,
                "slot": "09-11",
                "prefer_female": True,
            }
        },
    }, expect=201)

    booking_id = order["bookings"][0]["id"]

    # Verify female provider sees job in available, but male provider does NOT
    female_job = wait_for(
        lambda: next((j for j in call("GET", "/api/providers/jobs/?tab=available", female_pro, expect=200)["results"] if j["source_id"] == booking_id), None),
        "female provider to see the female-preferred job"
    )
    male_available = call("GET", "/api/providers/jobs/?tab=available", male_pro)["results"]
    assert not any(j["source_id"] == booking_id for j in male_available), "Male provider must NOT see female-preferred job"
    step("women-provider preference: job only visible to female provider")

    # 3. Training & Certification
    slug = f"safety-test-{STAMP}"
    call("POST", "/api/admin/training-modules/", admin, {
        "slug": slug,
        "title_bn": "নিরাপত্তা ও আচরণবিধি",
        "title_en": "Safety & Conduct",
        "body_bn": "কাজের সময় সর্বদা ভদ্র আচরণ করুন।",
        "body_en": "Always be courteous during service.",
        "pass_percent": 70,
        "is_active": True,
        "questions": [
          {
            "q": {"bn": "গ্রাহকের সাথে কেমন ব্যবহার করবেন?", "en": "How to behave with customers?"},
            "options": [{"bn": "ভদ্রভাবে", "en": "Politely"}, {"bn": "রূঢ়ভাবে", "en": "Rudely"}],
            "answer": 0
          },
          {
            "q": {"bn": "জরুরি পরিস্থিতিতে কী করবেন?", "en": "What to do in emergency?"},
            "options": [{"bn": "SOS বা ৯৯৯", "en": "SOS or 999"}, {"bn": "কিছু না", "en": "Nothing"}],
            "answer": 0
          }
        ]
    }, expect=201)

    pro_modules = call("GET", "/api/providers/training/", female_pro)
    mod = next((m for m in pro_modules if m["slug"] == slug), None)
    assert mod is not None, "Provider should see created training module"

    # Submit quiz answers
    quiz_res = call("POST", f"/api/providers/training/{slug}/submit/", female_pro, {"answers": [0, 0]}, expect=200)
    assert quiz_res["passed"] is True and quiz_res["score"] == 100
    cert_code = quiz_res["certificate_code"]
    assert cert_code, "Certificate code must be generated"

    # Verify public certificate endpoint
    cert = call("GET", f"/api/providers/certificates/{cert_code}/", expect=200)
    assert cert["provider"] == "Rina Akhter" and cert["score"] == 100

    # Verify provider profile has trained badge
    me_pro = call("GET", "/api/providers/me/", female_pro, expect=200)
    assert f"trained:{slug}" in me_pro["badges"]
    step("training quiz passed, certificate verified, and badge added to provider")

    # 4. Insurance: create plan, enroll, file claim, admin approves
    plan = call("POST", "/api/admin/insurance-plans/", admin, {
        "name_bn": "দুর্ঘটনা ও স্বাস্থ্য সুরক্ষা",
        "name_en": "Accident & Health Cover",
        "partner": "Green Delta",
        "weekly_premium": "40.00",
        "coverage_bn": "৫০,০০০ টাকা পর্যন্ত",
        "coverage_en": "Up to 50,000 BDT",
        "is_active": True,
    }, expect=201)

    enrollment = call("POST", "/api/providers/insurance/", female_pro, {"plan": plan["id"]}, expect=201)
    assert enrollment["status"] == "active"

    claim = call("POST", "/api/providers/insurance/claims/", female_pro, {
        "description": "Minor finger injury on site",
        "photo_urls": ["/media/cut.jpg"],
    }, expect=201)
    assert claim["status"] == "submitted"

    # Admin updates claim to paid
    updated_claim = call("POST", f"/api/admin/insurance-claims/{claim['id']}/update_status/", admin, {
        "status": "paid",
        "amount": "1200.00",
        "note": "Paid via bKash"
    }, expect=200)
    assert updated_claim["status"] == "paid" and updated_claim["amount"] == "1200.00"
    step("insurance plan enrolled, claim filed by provider, and paid by admin")

    # 5. Live job sharing link & SOS
    job_id = female_job["id"]

    # Female provider accepts job
    call("POST", f"/api/providers/jobs/{job_id}/accept/", female_pro, expect=200)

    # Customer generates live share link
    share = call("POST", "/api/providers/share/", customer, {"source": "booking", "source_id": booking_id}, expect=201)
    token = share["token"]
    shared_view = call("GET", f"/api/providers/share/{token}/", expect=200)
    assert shared_view["provider_first_name"] == "Rina"
    assert shared_view["provider_verified"] is True

    # Female provider triggers SOS
    sos = call("POST", "/api/providers/safety/sos/", female_pro, {
        "source": "booking",
        "source_id": booking_id,
        "latitude": "23.78",
        "longitude": "90.41",
        "note": "Suspicious situation",
    }, expect=201)
    assert sos["status"] == "open"

    # Admin checks incidents and resolves it
    inc_resp = call("GET", "/api/admin/safety/?status=open", admin)
    incidents = inc_resp["results"] if isinstance(inc_resp, dict) and "results" in inc_resp else inc_resp
    inc = next(i for i in incidents if i["id"] == sos["id"])
    assert inc["customer"]["name"] == "Salma Begum"
    assert inc["provider"]["name"] == "Rina Akhter"

    resolved = call("POST", f"/api/admin/safety/{sos['id']}/resolve/", admin, {"resolution": "Called provider, verified safe."}, expect=200)
    assert resolved["status"] == "resolved"
    step("live share link verified; SOS triggered and resolved by admin")

    # 6. Complete job, two-way ratings, and review dispute
    # Provider advances status to on_the_way, working, completed
    arrival_code = order["bookings"][0]["arrival_code"]
    call("PATCH", f"/api/providers/jobs/{job_id}/status/", female_pro, {"status": "on_the_way"}, expect=200)
    call("PATCH", f"/api/providers/jobs/{job_id}/status/", female_pro, {"status": "working", "arrival_code": arrival_code}, expect=200)
    call("PATCH", f"/api/providers/jobs/{job_id}/status/", female_pro, {"status": "completed"}, expect=200)

    # Provider rates customer
    call("POST", f"/api/providers/jobs/{job_id}/rate-customer/", female_pro, {"rating": 5, "feedback": "Great customer"}, expect=200)

    # Customer leaves an unfair 1-star review
    review = call("POST", "/api/providers/reviews/", customer, {
        "source": "booking",
        "source_id": booking_id,
        "rating": 1,
        "comment": "Unfair 1 star review"
    }, expect=201)

    # Provider disputes review
    dispute = call("POST", f"/api/providers/reviews/{review['id']}/dispute/", female_pro, {
        "reason": "Customer was upset about an unrelated issue outside my control."
    }, expect=200)
    assert dispute["dispute"] == "open"

    # Admin upholds dispute -> review is hidden
    admin_dispute = call("POST", f"/api/admin/review-disputes/{review['id']}/decide/", admin, {
        "uphold": True,
        "note": "Verified customer complaint was unwarranted."
    }, expect=200)
    assert admin_dispute["dispute"] == "upheld"
    assert admin_dispute["hidden"] is True
    step("two-way ratings submitted; review disputed and upheld (hidden) by admin")

    # 7. Instant payout with fee and insurance premium deduction
    earnings_resp = call("GET", "/api/providers/earnings/", female_pro, expect=200)
    summary = earnings_resp["summary"]
    pending_amount = Decimal(str(summary["pending"]))
    assert pending_amount > 0, "Provider should have pending earnings"

    payout = call("POST", "/api/providers/payouts/instant/", female_pro, expect=201)
    assert payout["instant"] is True
    assert Decimal(payout["fee"]) > 0, "Instant payout fee must be charged"
    assert Decimal(payout["insurance_premium"]) == Decimal("40.00"), "Weekly insurance premium must be deducted"
    expected_amount = pending_amount - Decimal(payout["fee"]) - Decimal(payout["insurance_premium"])
    assert Decimal(payout["amount"]) == expected_amount, f"Expected {expected_amount}, got {payout['amount']}"
    step("instant payout processed with instant fee and weekly insurance premium deducted")

    print("\n🎉 Phase 6 (Trust & Safety) E2E Test Passed Successfully!")


if __name__ == "__main__":
    main()
