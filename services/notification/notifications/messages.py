"""Event -> notifications. Each builder returns Note(...) items; sms=True also texts the user."""
from dataclasses import dataclass


@dataclass
class Note:
    user_id: int
    kind: str
    title_bn: str
    title_en: str
    body_bn: str = ""
    body_en: str = ""
    link: str = ""
    app: str = "customer"
    sms: bool = False


JOB_LINKS = {"booking": "/orders", "warranty": "/orders", "custom_request": "/custom-requests/{id}", "subscription_visit": "/subscriptions/mine"}
JOB_TEXT = {
    "accepted": ("প্রোভাইডার নিশ্চিত হয়েছে", "Provider confirmed", "{name} আপনার কাজটি নিয়েছেন।", "{name} has taken your job.", True),
    "on_the_way": ("প্রোভাইডার পথে আছেন", "Provider is on the way", "{name} রওনা দিয়েছেন। আগমন কোড তৈরি রাখুন।", "{name} is on the way. Keep your arrival code ready.", True),
    "completed": ("কাজ সম্পন্ন", "Job completed", "কাজ কেমন হলো? রেটিং দিন।", "How did it go? Leave a rating.", False),
}
ORDER_TEXT = {
    "confirmed": ("অর্ডার কনফার্মড", "Order confirmed"),
    "on_the_way": ("অর্ডার ডেলিভারিতে", "Order out for delivery"),
    "completed": ("অর্ডার সম্পন্ন", "Order completed"),
    "cancelled": ("অর্ডার বাতিল", "Order cancelled"),
}
CR_TEXT = {
    "under_review": ("রিকোয়েস্ট রিভিউ চলছে", "Request under review"),
    "provider_assigned": ("প্রোভাইডার নির্ধারিত", "Provider assigned"),
    "completed": ("কাস্টম কাজ সম্পন্ন", "Custom job completed"),
    "rejected": ("রিকোয়েস্ট গ্রহণ করা হয়নি", "Request declined"),
}
SUB_TEXT = {
    "active": ("সাবস্ক্রিপশন চালু", "Subscription active"),
    "paused": ("সাবস্ক্রিপশন বিরতিতে", "Subscription paused"),
    "cancelled": ("সাবস্ক্রিপশন বাতিল", "Subscription cancelled"),
    "expired": ("সাবস্ক্রিপশনের মেয়াদ শেষ", "Subscription ended"),
}


def build(event, p):
    if event == "order.placed":
        return [Note(p["user_id"], event, "অর্ডার পেয়েছি", "Order received", f"মোট ৳{p['total']}", f"Total ৳{p['total']}", f"/orders/{p['order_id']}", sms=True)]
    if event == "order.status_changed" and p["status"] in ORDER_TEXT:
        bn, en = ORDER_TEXT[p["status"]]
        return [Note(p["user_id"], event, bn, en, link=f"/orders/{p['order_id']}")]
    if event == "job.status_changed" and p["status"] in JOB_TEXT:
        tbn, ten, bbn, ben, sms = JOB_TEXT[p["status"]]
        name = p.get("provider_name") or "প্রোভাইডার"
        link = JOB_LINKS.get(p["source"], "/orders").format(id=p["source_id"])
        return [Note(p["user_id"], event, tbn, ten, bbn.format(name=name), ben.format(name=p.get("provider_name") or "The provider"), link, sms=sms)]
    if event == "booking.cancelled":
        return []
    if event == "order.landlord_approval_requested":
        return [Note(p["user_id"], event, "বাড়িওয়ালাকে অনুমতির লিংক পাঠানো হয়েছে", "Approval link sent to your landlord",
                     link=f"/orders/{p['order_id']}")]
    if event == "order.landlord_decided":
        if p["approved"]:
            return [Note(p["user_id"], event, "বাড়িওয়ালা মেরামতের খরচ ভাড়া থেকে কাটতে রাজি", "Landlord approved the rent deduction",
                         "রসিদটি অর্ডার পেজে পাবেন।", "The receipt is on the order page.", f"/orders/{p['order_id']}", sms=True)]
        return [Note(p["user_id"], event, "বাড়িওয়ালা ভাড়া থেকে কাটতে রাজি হননি", "Landlord declined the rent deduction",
                     link=f"/orders/{p['order_id']}", sms=True)]
    if event == "provider.approved":
        return [Note(p["user_id"], event, "আবেদন অনুমোদিত!", "Application approved!", "এখন থেকে আপনার এলাকার কাজ নিতে পারবেন।",
                     "You can now take jobs in your area.", "/", app="provider", sms=True)]
    if event == "safety.sos":
        who_bn = "প্রোভাইডার" if p["role"] == "provider" else "গ্রাহক"
        who_en = "Provider" if p["role"] == "provider" else "Customer"
        return [Note(uid, event, f"SOS: {who_bn} সাহায্য চাইছেন", f"SOS: {who_en} needs help",
                     f"{p['job_title']} · {p['area_name']}", f"{p['job_title']} · {p['area_name']}", "/safety", app="admin", sms=True)
                for uid in p.get("admin_ids", [])]
    if event == "emergency.raised":
        return [Note(uid, event, "জরুরি কাজ!", "Emergency job!", p["title"], p["title"], "/", app="provider", sms=True) for uid in p["provider_user_ids"]]
    if event == "custom_request.quoted":
        return [Note(p["user_id"], event, "আপনার কোট তৈরি", "Your quote is ready", f"মোট ৳{p['total']}", f"Total ৳{p['total']}",
                     f"/custom-requests/{p['request_id']}", sms=True)]
    if event == "custom_request.status_changed" and p["status"] in CR_TEXT:
        bn, en = CR_TEXT[p["status"]]
        return [Note(p["user_id"], event, bn, en, p.get("service_type", ""), p.get("service_type", ""), f"/custom-requests/{p['request_id']}")]
    if event == "subscription.created":
        return [Note(p["user_id"], event, "সাবস্ক্রিপশন তৈরি হয়েছে", "Subscription created", link="/subscriptions/mine")]
    if event == "subscription.status_changed" and p["status"] in SUB_TEXT:
        bn, en = SUB_TEXT[p["status"]]
        return [Note(p["user_id"], event, bn, en, link="/subscriptions/mine")]
    if event == "analytics.winback":
        body = p.get("message") or "আপনার বাসার কোনো কাজ বাকি থাকলে আমরা আছি — যাচাই করা প্রোভাইডার, ওয়ারেন্টিসহ।"
        return [Note(p["user_id"], event, "অনেকদিন দেখা নেই!", "We miss you!", body,
                     p.get("message") or "If anything at home needs fixing, we're here — verified providers, with warranty.", "/services")]
    if event == "home.reminder_due":
        return [Note(p["user_id"], event, p["title_bn"], p["title_en"], f"{p['due_date']} তারিখের মধ্যে করানো ভালো।",
                     f"Best done by {p['due_date']}.", f"/services/{p['service_slug']}", sms=True)]
    if event == "subscription.renewal_reminder":
        return [Note(p["user_id"], event, "সাবস্ক্রিপশন শীঘ্রই রিনিউ হবে", "Your subscription renews soon",
                     f"{p['end_date']} তারিখে মেয়াদ শেষ; স্বয়ংক্রিয়ভাবে রিনিউ হবে।", f"Ends on {p['end_date']} and renews automatically.",
                     "/subscriptions/mine", sms=True)]
    if event == "subscription.renewed":
        return [Note(p["user_id"], event, "সাবস্ক্রিপশন রিনিউ হয়েছে", "Subscription renewed", f"৳{p['amount']}", f"৳{p['amount']}", "/subscriptions/mine")]
    if event == "payment.succeeded":
        return [Note(p["user_id"], event, "পেমেন্ট সফল", "Payment successful", f"৳{p['amount']} পেয়েছি", f"We received ৳{p['amount']}", sms=True)]
    if event == "payment.failed":
        return [Note(p["user_id"], event, "পেমেন্ট হয়নি", "Payment failed", "আবার চেষ্টা করুন।", "Please try again.")]
    if event == "payment.refunded":
        return [Note(p["user_id"], event, "রিফান্ড হয়েছে", "Refund issued", f"৳{p['amount']} ফেরত পাঠানো হয়েছে", f"৳{p['amount']} has been refunded", sms=True)]
    if event == "chat.message":
        return [Note(p["user_id"], event, f"{p['from']}-এর বার্তা", f"Message from {p['from']}", p["preview"], p["preview"], f"/chat/{p['conversation_id']}")]
    if event == "loyalty.points_earned":
        return [Note(p["user_id"], event, f"{p['points']} পয়েন্ট পেয়েছেন", f"You earned {p['points']} points",
                     f"মোট {p['total']} পয়েন্ট", f"{p['total']} points in total", "/wallet")]
    if event == "b2b.invoice_issued":
        return [Note(p["user_id"], event, f"ইনভয়েস {p['number']}", f"Invoice {p['number']}", f"মোট ৳{p['total']}",
                     f"Total ৳{p['total']}", f"/business/{p['organization_id']}", sms=True)]
    if event == "issue.status_changed":
        return [Note(p["user_id"], event, "আপনার রিপোর্টের আপডেট", "Update on your report", p.get("title", ""), p.get("title", ""), f"/issues/{p['issue_id']}")]
    return []
