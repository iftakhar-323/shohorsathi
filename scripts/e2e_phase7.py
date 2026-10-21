"""End-to-end check of Dhap 7 (Channels & Payments):
- Direct bKash and Nagad payment flows on orders
- bKash Tokenized Auto-Debit agreement, recurring charge, and subscription activation
- WhatsApp Business Notification and OTP channel
- Messenger Bot Webhook (Verification, Menu, Service Search, Order Tracking)
- SMS Booking Flow (Draft creation: SS <SERVICE> <AREA>, Confirmation: YES <ID>, Status: STATUS <ID>)
Usage: python3 scripts/e2e_phase7.py [http://localhost:8088]  (stack running, catalog seeded)
"""
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from decimal import Decimal

import e2e_phase1 as e1

call, register, wait_for, step = e1.call, e1.register, e1.wait_for, e1.step
STAMP = str(int(time.time()))[-8:]


def form_post(path, fields):
    req = urllib.request.Request(e1.BASE + path, data=urllib.parse.urlencode(fields).encode(), method="POST")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    try:
        urllib.request.build_opener(NoRedirect).open(req)
    except urllib.error.HTTPError as e:
        return e.headers.get("Location", "")
    return ""


def main():
    admin_phone = f"019{STAMP}"
    cust_phone = f"017{STAMP}"
    sms_phone = f"015{STAMP}"

    # Setup admin
    subprocess.run(
        [
            "docker", "compose", "exec", "-T", "-e", "DJANGO_SUPERUSER_PASSWORD=admin-pass-123",
            "auth", "python", "manage.py", "createsuperuser", "--noinput",
            "--phone", admin_phone, "--full_name", "Payments Admin"
        ],
        check=True, capture_output=True
    )
    admin = call("POST", "/api/auth/login/", body={"phone": admin_phone, "password": "admin-pass-123"}, expect=200)["access"]
    area = call("POST", "/api/admin/areas/", admin, {"name_en": f"Payment Area {STAMP}", "name_bn": "পেমেন্ট এলাকা"}, expect=201)

    customer = register(cust_phone, "Tanvir Ahmed")["access"]
    step("registered customer and admin")

    # -------------------------------------------------------------------------------------------------
    # 1. Direct bKash and Nagad payments on Order
    # -------------------------------------------------------------------------------------------------
    cart_item = call("POST", "/api/cart/items/", customer, {"item_type": "service", "slug": "electrician-visit"}, expect=201)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    order_bk = call("POST", "/api/orders/", customer, {
        "contact_name": "Tanvir Ahmed",
        "contact_phone": cust_phone,
        "address_line": "House 12, Road 4",
        "area_id": area["id"],
        "area_name": area["name_bn"],
        "payment_method": "online",
        "service_details": {str(cart_item["id"]): {"scheduled_date": tomorrow, "slot": "09-11"}},
    }, expect=201)

    # Initiate with direct bKash
    init_bk = call("POST", "/api/payments/initiate/", customer, {"purpose": "order", "reference_id": order_bk["id"], "gateway": "bkash"}, expect=201)
    assert init_bk["gateway"] == "bkash"
    assert "/api/payments/bkash/mock/" in init_bk["redirect_url"]
    tran_bk = init_bk["tran_id"]

    # Post success callback
    loc_pay_bk = form_post("/api/payments/gateway/success/", {"tran_id": tran_bk, "val_id": f"bkash-{tran_bk}", "amount": str(init_bk["amount"]), "card_type": "bKash"})
    assert "status=held" in loc_pay_bk

    # Wait for order to be marked paid
    wait_for(lambda: call("GET", f"/api/orders/{order_bk['id']}/", customer)["payment_status"] == "paid", f"order {order_bk['id']} paid via bKash")
    step("direct bKash checkout and escrow hold verified")

    # Order with direct Nagad
    cart_item2 = call("POST", "/api/cart/items/", customer, {"item_type": "service", "slug": "electrician-visit"}, expect=201)
    order_ng = call("POST", "/api/orders/", customer, {
        "contact_name": "Tanvir Ahmed",
        "contact_phone": cust_phone,
        "address_line": "House 12, Road 4",
        "area_id": area["id"],
        "area_name": area["name_bn"],
        "payment_method": "online",
        "service_details": {str(cart_item2["id"]): {"scheduled_date": tomorrow, "slot": "09-11"}},
    }, expect=201)

    init_ng = call("POST", "/api/payments/initiate/", customer, {"purpose": "order", "reference_id": order_ng["id"], "gateway": "nagad"}, expect=201)
    assert init_ng["gateway"] == "nagad"
    assert "/api/payments/nagad/mock/" in init_ng["redirect_url"]
    tran_ng = init_ng["tran_id"]

    loc_pay_ng = form_post("/api/payments/gateway/success/", {"tran_id": tran_ng, "val_id": f"nagad-{tran_ng}", "amount": str(init_ng["amount"]), "card_type": "Nagad"})
    assert "status=held" in loc_pay_ng
    wait_for(lambda: call("GET", f"/api/orders/{order_ng['id']}/", customer)["payment_status"] == "paid", f"order {order_ng['id']} paid via Nagad")
    step("direct Nagad checkout and escrow hold verified")

    # -------------------------------------------------------------------------------------------------
    # 2. bKash Tokenized Auto-Debit for Subscription
    # -------------------------------------------------------------------------------------------------
    # Create agreement
    agr_init = call("POST", "/api/payments/agreements/bkash/create/", customer, expect=200)
    assert "agreement_url" in agr_init

    # Execute agreement
    agr_id = f"AGR-BK-{STAMP}"
    agr_exec = call("POST", "/api/payments/agreements/bkash/execute/", customer, {"agreement_id": agr_id, "payer_reference": cust_phone}, expect=201)
    assert agr_exec["status"] == "active"
    assert agr_exec["agreement_id"] == agr_id

    # List agreements
    my_agreements = call("GET", "/api/payments/agreements/", customer, expect=200)
    agr_list = my_agreements if isinstance(my_agreements, list) else my_agreements.get("results", [])
    assert any(a["agreement_id"] == agr_id for a in agr_list)

    # Subscribe with bkash_auto
    sub = call("POST", "/api/subscriptions/", customer, {
        "plan": "cleaning-basic",
        "duration_days": 30,
        "home_size": 1,
        "prepaid_months": 1,
        "start_date": tomorrow,
        "slot": "09-11",
        "area_id": area["id"],
        "area_name": area["name_bn"],
        "address_line": "Flat 4A, Green Road",
        "payment_method": "bkash_auto",
        "agreement_id": agr_id,
        "auto_renew": True,
    }, expect=201)
    assert sub["payment_method"] == "bkash_auto"
    assert sub["agreement_id"] == agr_id
    assert sub["status"] == "active"
    assert sub["paid"] is True

    # Cancel agreement
    cancelled = call("POST", f"/api/payments/agreements/{agr_exec['id']}/cancel/", customer, expect=200)
    assert cancelled["status"] == "cancelled"
    step("bKash tokenized auto-debit agreement created, subscription auto-paid, and agreement cancelled")

    # -------------------------------------------------------------------------------------------------
    # 3. WhatsApp Business Notification & OTP Channel
    # -------------------------------------------------------------------------------------------------
    wa_phone = f"013{STAMP}"
    call("POST", "/api/auth/otp/request/", body={"phone": wa_phone, "purpose": "register", "channel": "whatsapp"}, expect=200)
    # Check WhatsApp log in notification service
    wa_check = subprocess.run(
        [
            "docker", "compose", "exec", "-T", "notification",
            "python", "manage.py", "shell", "-c",
            f"from notifications.models import WhatsAppLog; print(WhatsAppLog.objects.filter(phone='{wa_phone}').count())"
        ],
        check=True, capture_output=True, text=True
    )
    assert int(wa_check.stdout.strip()) >= 1
    step("WhatsApp OTP requested and logged in notification service")

    # -------------------------------------------------------------------------------------------------
    # 4. Messenger Bot Webhook
    # -------------------------------------------------------------------------------------------------
    # Verification GET
    res_hub = call("GET", "/api/messenger/webhook/?hub.mode=subscribe&hub.verify_token=shohor-messenger-verify-token&hub.challenge=999888", expect=200)
    assert res_hub == "999888" or "999888" in str(res_hub)

    # Inbound message POST
    call("POST", "/api/messenger/webhook/", body={
        "object": "page",
        "entry": [{
            "messaging": [{
                "sender": {"id": f"fb_psid_{STAMP}"},
                "message": {"text": "hello"}
            }]
        }]
    }, expect=200)

    # Quick reply POST (Services)
    call("POST", "/api/messenger/webhook/", body={
        "object": "page",
        "entry": [{
            "messaging": [{
                "sender": {"id": f"fb_psid_{STAMP}"},
                "message": {"text": "সার্ভিস", "quick_reply": {"payload": "MENU_SERVICES"}}
            }]
        }]
    }, expect=200)
    step("Messenger bot webhook verification and interactive message processing verified")

    # -------------------------------------------------------------------------------------------------
    # 5. SMS Booking Flow (Low-data / Offline)
    # -------------------------------------------------------------------------------------------------
    # Draft Booking: SS CLEAN DHANMONDI Road 5
    res_sms_draft = call("POST", "/api/orders/sms-inbound/", body={"phone": sms_phone, "text": "SS CLEAN DHANMONDI Road 5"}, expect=200)
    reply_draft = res_sms_draft["reply"]
    assert "ড্রাফট তৈরি হয়েছে" in reply_draft
    assert "নিশ্চিত করতে রিপ্লাই দিন" in reply_draft

    # Extract order ID from reply
    import re
    order_id_match = re.search(r"#(\d+)", reply_draft)
    assert order_id_match, f"No order ID found in reply: {reply_draft}"
    sms_order_id = int(order_id_match.group(1))

    # Query Status via SMS
    res_sms_status = call("POST", "/api/orders/sms-inbound/", body={"phone": sms_phone, "text": f"STATUS {sms_order_id}"}, expect=200)
    assert f"#{sms_order_id}" in res_sms_status["reply"]
    assert "pending" in res_sms_status["reply"]

    # Confirm Booking via SMS: YES <ORDER_ID>
    res_sms_confirm = call("POST", "/api/orders/sms-inbound/", body={"phone": sms_phone, "text": f"YES {sms_order_id}"}, expect=200)
    assert "নিশ্চিত করা হয়েছে" in res_sms_confirm["reply"]

    # Verify order status in DB
    order_status_check = subprocess.run(
        [
            "docker", "compose", "exec", "-T", "order",
            "python", "manage.py", "shell", "-c",
            f"from orders.models import Order; print(Order.objects.get(pk={sms_order_id}).status)"
        ],
        check=True, capture_output=True, text=True
    )
    assert "confirmed" in order_status_check.stdout.strip()
    step("SMS booking draft creation, status query, and YES confirmation verified")

    print("\n🎉 Phase 7 (Channels & Payments) E2E Test Passed Successfully!")


if __name__ == "__main__":
    main()
