"""Payment gateways: SSLCommerz, direct bKash (including tokenized agreements for recurring auto-debit),
and direct Nagad. In development, mock pages provide realistic interactive payment flows."""
import secrets
from decimal import Decimal

import requests
from django.conf import settings


class GatewayError(Exception):
    pass


class MockGateway:
    name = "mock"

    def start(self, payment, customer):
        return f"{settings.PUBLIC_API_URL}/api/payments/mock/{payment.tran_id}/"

    def validate(self, data):
        # The mock page posts val_id = "mock-<tran_id>"; anything else is rejected.
        tran_id = data.get("tran_id", "")
        ok = data.get("val_id") == f"mock-{tran_id}"
        return {
            "ok": ok,
            "amount": Decimal(data.get("amount", "0")) if ok else None,
            "val_id": data.get("val_id", ""),
            "bank_tran_id": f"MOCK{tran_id[-6:]}",
            "method": data.get("card_type", "Card / MFS (mock)"),
        }

    def refund(self, payment, amount, reason):
        return f"MOCKREF{payment.tran_id[-6:]}"


class BkashGateway:
    name = "bkash"

    def start(self, payment, customer):
        return f"{settings.PUBLIC_API_URL}/api/payments/bkash/mock/{payment.tran_id}/"

    def validate(self, data):
        tran_id = data.get("tran_id", "")
        ok = data.get("val_id") == f"bkash-{tran_id}"
        return {
            "ok": ok,
            "amount": Decimal(data.get("amount", "0")) if ok else None,
            "val_id": data.get("val_id", ""),
            "bank_tran_id": f"BK{tran_id[-6:]}",
            "method": "bKash",
        }

    def refund(self, payment, amount, reason):
        return f"BKREF{payment.tran_id[-6:]}"

    def start_agreement(self, user):
        ref = user.get("phone") or str(user.get("id"))
        return {
            "agreement_url": f"{settings.PUBLIC_API_URL}/api/payments/bkash/agreement/mock/?user_id={user['id']}&phone={ref}",
            "payer_reference": ref,
        }

    def execute_agreement(self, agreement_id, payer_reference=""):
        return {"ok": True, "agreement_id": agreement_id, "payer_reference": payer_reference}

    def charge_agreement(self, agreement_id, amount, tran_id):
        return {
            "ok": True,
            "val_id": f"bkash-auto-{tran_id}",
            "bank_tran_id": f"BKAUTO{tran_id[-6:]}",
            "method": "bKash Auto-Debit",
        }


class NagadGateway:
    name = "nagad"

    def start(self, payment, customer):
        return f"{settings.PUBLIC_API_URL}/api/payments/nagad/mock/{payment.tran_id}/"

    def validate(self, data):
        tran_id = data.get("tran_id", "")
        ok = data.get("val_id") == f"nagad-{tran_id}"
        return {
            "ok": ok,
            "amount": Decimal(data.get("amount", "0")) if ok else None,
            "val_id": data.get("val_id", ""),
            "bank_tran_id": f"NG{tran_id[-6:]}",
            "method": "Nagad",
        }

    def refund(self, payment, amount, reason):
        return f"NGREF{payment.tran_id[-6:]}"


class SSLCommerzGateway:
    name = "sslcommerz"

    def __init__(self):
        self.base = "https://sandbox.sslcommerz.com" if settings.SSLCOMMERZ_SANDBOX else "https://securepay.sslcommerz.com"
        self.store_id = settings.SSLCOMMERZ_STORE_ID
        self.store_pass = settings.SSLCOMMERZ_STORE_PASSWORD

    def start(self, payment, customer):
        api = settings.PUBLIC_API_URL
        body = {
            "store_id": self.store_id,
            "store_passwd": self.store_pass,
            "total_amount": str(payment.amount),
            "currency": payment.currency,
            "tran_id": payment.tran_id,
            "success_url": f"{api}/api/payments/gateway/success/",
            "fail_url": f"{api}/api/payments/gateway/fail/",
            "cancel_url": f"{api}/api/payments/gateway/cancel/",
            "ipn_url": f"{api}/api/payments/gateway/ipn/",
            "product_name": payment.get_purpose_display(),
            "product_category": "service",
            "product_profile": "general",
            "shipping_method": "NO",
            "cus_name": customer.get("name") or "Customer",
            "cus_phone": customer.get("phone") or "",
            "cus_email": "customer@shohorsathi.local",
            "cus_add1": "Dhaka",
            "cus_city": "Dhaka",
            "cus_country": "Bangladesh",
            "value_a": payment.purpose,
            "value_b": str(payment.reference_id),
        }
        try:
            res = requests.post(f"{self.base}/gwprocess/v4/api.php", data=body, timeout=15).json()
        except (requests.RequestException, ValueError) as e:
            raise GatewayError("SSLCommerz unreachable") from e
        if res.get("status") != "SUCCESS" or not res.get("GatewayPageURL"):
            raise GatewayError(res.get("failedreason", "SSLCommerz refused the session"))
        return res["GatewayPageURL"]

    def validate(self, data):
        val_id = data.get("val_id")
        if not val_id:
            return {"ok": False}
        params = {"val_id": val_id, "store_id": self.store_id, "store_passwd": self.store_pass, "format": "json"}
        try:
            res = requests.get(f"{self.base}/validator/api/validationserverAPI.php", params=params, timeout=15).json()
        except (requests.RequestException, ValueError) as e:
            raise GatewayError("SSLCommerz validation unreachable") from e
        ok = res.get("status") in ("VALID", "VALIDATED") and res.get("tran_id") == data.get("tran_id")
        return {"ok": ok, "amount": Decimal(res.get("amount", "0")), "val_id": val_id,
                "bank_tran_id": res.get("bank_tran_id", ""), "method": res.get("card_type", ""), "raw": res}

    def refund(self, payment, amount, reason):
        params = {"bank_tran_id": payment.bank_tran_id, "refund_amount": str(amount), "refund_remarks": reason[:250],
                  "store_id": self.store_id, "store_passwd": self.store_pass, "format": "json"}
        try:
            res = requests.get(f"{self.base}/validator/api/merchantTransIDvalidationAPI.php", params=params, timeout=15).json()
        except (requests.RequestException, ValueError) as e:
            raise GatewayError("SSLCommerz refund unreachable") from e
        if res.get("APIConnect") != "DONE" or res.get("status") not in ("success", "processing"):
            raise GatewayError(res.get("errorReason", "Refund refused"))
        return res.get("refund_ref_id", "")


GATEWAYS = {
    "mock": MockGateway,
    "bkash": BkashGateway,
    "nagad": NagadGateway,
    "sslcommerz": SSLCommerzGateway,
}


def get_gateway(name=None):
    if name and name in GATEWAYS:
        cls = GATEWAYS[name]
        return cls()
    return SSLCommerzGateway() if settings.PAYMENT_GATEWAY == "sslcommerz" else MockGateway()


def gateway():
    return get_gateway()
