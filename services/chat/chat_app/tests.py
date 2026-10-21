import pytest
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from shohor_common import internal
from shohor_common.testing import auth_client, token

from chat_app.models import Conversation

JOB = {"job_id": 1, "title": "Fan repair", "status": "accepted", "customer_user_id": 7, "provider_user_id": 50, "provider_name": "Karim"}


@pytest.fixture(autouse=True)
def provider_service(monkeypatch):
    monkeypatch.setattr(internal, "get", lambda service, path, **kw: JOB if path.endswith("/booking/10/") else None)


@pytest.fixture
def customer():
    return auth_client("customer", user_id=7, name="Rahim")


@pytest.fixture
def provider():
    return auth_client("provider", user_id=50, name="Karim")


def open_job(client):
    return client.post("/api/chat/conversations/", {"kind": "job", "source": "booking", "source_id": 10}, format="json")


@pytest.mark.django_db
def test_job_chat_between_customer_and_provider(customer, provider, captured_events):
    conv = open_job(customer).data
    assert open_job(provider).data["id"] == conv["id"]  # same conversation for both
    customer.post(f"/api/chat/conversations/{conv['id']}/messages/", {"body": "কখন আসবেন?"}, format="json")
    assert captured_events[-1] == ("chat.message", {"conversation_id": conv["id"], "user_id": 50, "from": "Rahim", "preview": "কখন আসবেন?"})
    assert provider.get("/api/chat/unread/").data == {"unread": 1}
    msgs = provider.get(f"/api/chat/conversations/{conv['id']}/messages/").data["messages"]
    assert msgs[0]["sender_role"] == "customer"
    assert provider.get("/api/chat/unread/").data == {"unread": 0}


@pytest.mark.django_db
def test_outsider_cannot_open_or_read(customer):
    stranger = auth_client("customer", user_id=99)
    assert open_job(stranger).status_code == 403
    conv = open_job(customer).data
    assert stranger.get(f"/api/chat/conversations/{conv['id']}/messages/").status_code == 404


@pytest.mark.django_db
def test_support_chat_gets_faq_answer_and_admin_reply(customer):
    conv = customer.post("/api/chat/conversations/", {"kind": "support", "subject": "Refund", "body": "আমার refund কবে পাব?"}, format="json").data
    msgs = customer.get(f"/api/chat/conversations/{conv['id']}/messages/").data["messages"]
    assert [m["sender_role"] for m in msgs] == ["customer", "bot"] and "রিফান্ড" in msgs[1]["body"]
    admin = auth_client("admin", user_id=1, name="Support")
    assert [c["id"] for c in admin.get("/api/admin/chat/support/").data] == [conv["id"]]
    admin.post(f"/api/chat/conversations/{conv['id']}/messages/", {"body": "Processing it now."}, format="json")
    admin.post(f"/api/admin/chat/support/{conv['id']}/close/")
    assert customer.post(f"/api/chat/conversations/{conv['id']}/messages/", {"body": "ok"}, format="json").status_code == 400


@pytest.mark.django_db(transaction=True)
def test_websocket_receives_new_messages(customer):
    from config.asgi import application

    conv_id = open_job(customer).data["id"]

    async def run():
        bad = WebsocketCommunicator(application, f"/api/chat/ws/{conv_id}/?token={token('customer', 99)}")
        connected, _ = await bad.connect()
        assert not connected
        ws = WebsocketCommunicator(application, f"/api/chat/ws/{conv_id}/?token={token('provider', 50)}")
        connected, _ = await ws.connect()
        assert connected
        from channels.db import database_sync_to_async

        await database_sync_to_async(customer.post)(f"/api/chat/conversations/{conv_id}/messages/", {"body": "hello"}, format="json")
        message = await ws.receive_json_from(timeout=2)
        await ws.disconnect()
        return message

    assert async_to_sync(run)()["body"] == "hello"
    assert Conversation.objects.count() == 1
