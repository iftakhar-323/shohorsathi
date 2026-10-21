"""Messenger Bot for ShohorSathi (শহরসাথী).
Handles Facebook/Meta Messenger webhooks: verification, automated customer assistance,
catalog service discovery, order tracking, emergency helpline, and FAQ quick replies."""
import logging
import re

import requests
from django.conf import settings
from shohor_common import internal

log = logging.getLogger(__name__)

# Mock outbox for testing and dev inspection
OUTBOX = []


def verify_webhook(mode, token, challenge):
    if mode == "subscribe" and token == settings.MESSENGER_VERIFY_TOKEN:
        return challenge
    return None


def format_quick_replies():
    return [
        {"content_type": "text", "title": "🔍 সার্ভিস খুঁজুন", "payload": "MENU_SERVICES"},
        {"content_type": "text", "title": "📦 অর্ডার ট্র্যাকিং", "payload": "MENU_TRACK"},
        {"content_type": "text", "title": "🚨 জরুরি সেবা", "payload": "MENU_EMERGENCY"},
        {"content_type": "text", "title": "💬 সাপোর্ট", "payload": "MENU_SUPPORT"},
    ]


def handle_message(sender_id, text="", payload=""):
    text_clean = (text or "").strip().lower()
    payload = payload or ""
    web_url = getattr(settings, "CUSTOMER_WEB_URL", "http://localhost:5173")

    if payload == "MENU_SERVICES" or any(w in text_clean for w in ["সার্ভিস", "service", "services", "সেবা"]):
        msg = ("শহরসাথীর জনপ্রিয় সার্ভিসসমূহ:\n"
               "১. বাসা ডিপ ক্লিনিং ও সাধারণ পরিষ্কার\n"
               "২. এসি রিপেয়ার ও সার্ভিসিং\n"
               "৩. প্লাম্বিং ও পাইপলাইন মেরামত\n"
               "৪. ইলেকট্রিক্যাল ওয়্যারিং ও ফ্যান মেরামত\n"
               "৫. হোম শেফ ও মিল সাবস্ক্রিপশন\n\n"
               f"সরাসরি বুক করতে ভিজিট করুন: {web_url}/services")
        return {"text": msg, "quick_replies": format_quick_replies()}

    if payload == "MENU_TRACK" or "track" in text_clean or "ট্র্যাক" in text_clean:
        match = re.search(r"\d+", text_clean)
        if match:
            order_id = int(match.group())
            try:
                order_info = internal.get("order", f"/api/internal/orders/{order_id}/summary/")
            except Exception:
                order_info = None

            if order_info:
                st = order_info.get("status_bn") or order_info.get("status")
                p_name = order_info.get("provider_name") or "এখনো নির্ধারিত হয়নি"
                msg = (f"অর্ডার #{order_id} এর তথ্য:\n"
                       f"স্ট্যাটাস: {st}\n"
                       f"প্রোভাইডার: {p_name}\n"
                       f"বিস্তারিত ট্র্যাকিং: {web_url}/orders/{order_id}")
            else:
                msg = (f"অর্ডার #{order_id} এর স্ট্যাটাস দেখতে এবং লাইভ ম্যাপ দেখতে ভিজিট করুন:\n"
                       f"{web_url}/orders/{order_id}")
            return {"text": msg, "quick_replies": format_quick_replies()}

        return {
            "text": "আপনার অর্ডার ট্র্যাক করতে অর্ডার নম্বরটি লিখে পাঠান (যেমন: 'track 12' অথবা শুধু '12')।",
            "quick_replies": format_quick_replies(),
        }

    if payload == "MENU_EMERGENCY" or any(w in text_clean for w in ["জরুরি", "emergency", "sos", "বিপদ"]):
        msg = ("🚨 শহরসাথী জরুরি সহায়তা:\n"
               "জরুরি হোম সেবার জন্য ১-ট্যাপ রিকোয়েস্ট পাঠান:\n"
               f"{web_url}/emergency\n\n"
               "অথবা জরুরি জাতীয় হেল্পলাইন ৯৯৯ এ কল করুন। শহরসাথী হেল্পলাইন: ১৬XXX")
        return {"text": msg, "quick_replies": format_quick_replies()}

    if payload == "MENU_SUPPORT" or any(w in text_clean for w in ["support", "সাপোর্ট", "help", "সাহায্য"]):
        msg = ("💬 শহরসাথী কাস্টমার সাপোর্ট:\n"
               "আমাদের সাপোর্ট টিম সকাল ৮টা থেকে রাত ১১টা পর্যন্ত আপনার সেবায় নিয়োজিত।\n"
               "আপনার কোনো প্রশ্ন বা অভিযোগ থাকলে বিস্তারিত লিখুন, আমাদের টিম দ্রুত রিপ্লাই দিবে।")
        return {"text": msg, "quick_replies": format_quick_replies()}

    # Check for direct order ID query (e.g. "12")
    if text_clean.isdigit():
        order_id = int(text_clean)
        msg = (f"অর্ডার #{order_id} এর ট্র্যাকিং ও বিস্তারিত:\n"
               f"{web_url}/orders/{order_id}")
        return {"text": msg, "quick_replies": format_quick_replies()}

    # Greeting / Default
    msg = ("স্বাগতম ShohorSathi (শহরসাথী)-তে! 🏙️\n"
           "শহরের সকল নির্ভরযোগ্য হোম সার্ভিস ও সমস্যা সমাধানের বিশ্বস্ত প্ল্যাটফর্ম।\n\n"
           "আপনি কী করতে চান? নিচের মেনু থেকে বেছে নিন অথবা লিখে জানান:")
    return {"text": msg, "quick_replies": format_quick_replies()}


def send_reply(recipient_id, message_data):
    backend = getattr(settings, "MESSENGER_BACKEND", "mock")
    token = getattr(settings, "MESSENGER_PAGE_ACCESS_TOKEN", "")

    if backend == "cloud" and token:
        url = f"https://graph.facebook.com/v18.0/me/messages?access_token={token}"
        payload = {"recipient": {"id": recipient_id}, "message": message_data}
        try:
            requests.post(url, json=payload, timeout=10)
        except requests.RequestException as e:
            log.warning("failed to send messenger message: %s", e)
    else:
        log.info("Messenger reply to %s: %s", recipient_id, message_data)
        OUTBOX.append({"recipient_id": recipient_id, "message": message_data})

