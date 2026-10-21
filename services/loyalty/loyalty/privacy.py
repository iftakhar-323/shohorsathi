from shohor_common.privacy import iso

from .models import Account, Entry


def collect(user_id):
    """Export only: the ledger keeps just user ids and is an accounting record."""
    acc = Account.objects.filter(user_id=user_id).first()
    return {
        "points": acc.points if acc else 0,
        "credit": str(acc.wallet) if acc else "0",
        "referral_code": acc.referral_code if acc else None,
        "history": [{"kind": e.kind, "delta": str(e.delta), "reason": e.reason, "at": iso(e.created_at)} for e in Entry.objects.filter(user_id=user_id)],
    }
