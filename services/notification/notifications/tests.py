import pytest
from shohor_common import internal
from shohor_common.testing import auth_client

from notifications import logic, tasks
from notifications.models import Notification, SmsLog


@pytest.fixture(autouse=True)
def auth_service(monkeypatch):
    def fake(service, path, **kw):
        if path == "/api/internal/users/":
            return {"ids": [7, 8]}
        return {"id": 7, "phone": "01712345678", "full_name": "Rahim"}

    monkeypatch.setattr(internal, "get", fake)


@pytest.mark.django_db
def test_job_event_notifies_and_texts_customer():
    logic.handle("job.status_changed", {"user_id": 7, "source": "booking", "source_id": 3, "status": "on_the_way", "provider_name": "Karim"})
    n = Notification.objects.get()
    assert n.title_en == "Provider is on the way" and "Karim" in n.body_bn
    assert SmsLog.objects.get().phone == "01712345678"


@pytest.mark.django_db
def test_every_subscribed_event_has_a_task():
    assert "notification.payment.refunded" in {t.name for t in tasks.TASKS.values()}


@pytest.mark.django_db
def test_list_unread_and_read_all():
    logic.handle("order.placed", {"user_id": 7, "order_id": 1, "total": "500"})
    logic.handle("payment.failed", {"user_id": 7})
    client = auth_client(user_id=7)
    assert client.get("/api/notifications/unread-count/").data == {"unread": 2}
    assert len(client.get("/api/notifications/").data["results"]) == 2
    client.post("/api/notifications/read-all/")
    assert client.get("/api/notifications/unread-count/").data == {"unread": 0}
    assert auth_client(user_id=8).get("/api/notifications/").data["count"] == 0


@pytest.mark.django_db
def test_admin_broadcast():
    admin = auth_client("admin")
    res = admin.post("/api/admin/notifications/broadcast/", {"audience": "customers", "title_bn": "ঈদ অফার", "title_en": "Eid offer"}, format="json")
    assert res.data["sent_count"] == 2 and Notification.objects.filter(kind="promo").count() == 2
    assert auth_client().post("/api/admin/notifications/broadcast/", {}, format="json").status_code == 403
