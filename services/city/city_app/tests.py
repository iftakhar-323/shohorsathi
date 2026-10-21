import pytest
from rest_framework.test import APIClient
from shohor_common.testing import auth_client

from city_app.models import Authority, Issue

SPOT = {"category": "streetlight", "title": "Broken streetlight", "latitude": "23.810331", "longitude": "90.412521",
        "area_id": 3, "area_name": "Mirpur", "photo_urls": ["/media/public/x.jpg"]}


@pytest.fixture
def reporter():
    return auth_client(user_id=7, name="Rahim")


@pytest.mark.django_db
def test_report_needs_photo_and_counts_own_upvote(reporter):
    assert reporter.post("/api/issues/", {**SPOT, "photo_urls": []}, format="json").status_code == 400
    res = reporter.post("/api/issues/", SPOT, format="json")
    assert res.status_code == 201 and res.data["upvote_count"] == 1 and res.data["status"] == "reported"


@pytest.mark.django_db
def test_duplicate_nearby_is_suggested(reporter):
    first = reporter.post("/api/issues/", SPOT, format="json").data
    nearby = {**SPOT, "latitude": "23.810500"}  # ~19 m away
    dup = auth_client(user_id=8).post("/api/issues/", nearby, format="json")
    assert dup.status_code == 409 and dup.data["duplicate"]["id"] == first["id"]
    forced = auth_client(user_id=8).post("/api/issues/", {**nearby, "force": True}, format="json")
    assert forced.status_code == 201
    far = auth_client(user_id=8).post("/api/issues/", {**SPOT, "latitude": "23.830000"}, format="json")
    assert far.status_code == 201


@pytest.mark.django_db
def test_public_list_near_and_map(reporter):
    reporter.post("/api/issues/", SPOT, format="json")
    reporter.post("/api/issues/", {**SPOT, "category": "garbage", "latitude": "23.900000"}, format="json")
    anon = APIClient()
    near = anon.get("/api/issues/?near=23.8103,90.4125&radius_km=1").data
    assert near["count"] == 1 and near["results"][0]["distance_km"] < 0.1
    assert len(anon.get("/api/issues/map/").data) == 2


@pytest.mark.django_db
def test_upvote_toggle(reporter):
    issue_id = reporter.post("/api/issues/", SPOT, format="json").data["id"]
    other = auth_client(user_id=8)
    assert other.post(f"/api/issues/{issue_id}/upvote/").data == {"upvoted": True, "upvote_count": 2}
    assert other.post(f"/api/issues/{issue_id}/upvote/").data == {"upvoted": False, "upvote_count": 1}
    assert APIClient().post(f"/api/issues/{issue_id}/upvote/").status_code == 401


@pytest.mark.django_db
def test_admin_forward_and_resolve_notifies_upvoters(reporter, captured_events):
    issue_id = reporter.post("/api/issues/", SPOT, format="json").data["id"]
    auth_client(user_id=8).post(f"/api/issues/{issue_id}/upvote/")
    office = Authority.objects.create(name_bn="ওয়ার্ড ৫ অফিস", name_en="Ward 5 office", categories=["streetlight"])
    admin = auth_client("admin")
    assert admin.post(f"/api/admin/issues/{issue_id}/status/", {"status": "forwarded"}, format="json").status_code == 400
    res = admin.post(f"/api/admin/issues/{issue_id}/status/", {"status": "forwarded", "authority": office.id}, format="json")
    assert res.data["authority_name"]["en"] == "Ward 5 office"
    admin.post(f"/api/admin/issues/{issue_id}/status/", {"status": "resolved", "photos": ["/media/public/fixed.jpg"]}, format="json")
    issue = Issue.objects.get()
    assert issue.status == "resolved" and issue.resolved_photo_urls == ["/media/public/fixed.jpg"]
    notified = {p["user_id"] for e, p in captured_events if e == "issue.status_changed" and p["status"] == "resolved"}
    assert notified == {7, 8}
    assert [u["status"] for u in reporter.get(f"/api/issues/{issue_id}/").data["updates"]] == ["reported", "forwarded", "resolved"]


@pytest.mark.django_db
def test_community_post_like_comment(reporter):
    post = reporter.post("/api/community/posts/", {"area_id": 3, "area_name": "Mirpur", "kind": "tip", "body": "Load-shedding 6–8pm"}, format="json").data
    other = auth_client(user_id=8, name="Karim")
    assert other.post(f"/api/community/posts/{post['id']}/like/").data["like_count"] == 1
    other.post(f"/api/community/posts/{post['id']}/comments/", {"body": "ধন্যবাদ"}, format="json")
    feed = APIClient().get("/api/community/posts/?area=3").data["results"]
    assert feed[0]["comment_count"] == 1 and feed[0]["author_name"] == "Rahim"
    assert other.delete(f"/api/community/posts/{post['id']}/").status_code == 403
    auth_client("admin").post(f"/api/admin/community/posts/{post['id']}/hide/")
    assert APIClient().get("/api/community/posts/").data["count"] == 0


@pytest.mark.django_db
def test_user_deleted_keeps_issue_but_drops_posts(reporter):
    from city_app.models import Post
    from city_app.tasks import user_deleted

    reporter.post("/api/issues/", SPOT, format="json")
    reporter.post("/api/community/posts/", {"area_id": 3, "area_name": "Mirpur", "kind": "tip", "body": "x"}, format="json")
    user_deleted({"user_id": 7})
    assert Issue.objects.get().reporter_name == "" and not Post.objects.exists()


@pytest.mark.django_db
def test_transparency_report_has_no_personal_data(reporter):
    from django.utils import timezone

    first = reporter.post("/api/issues/", SPOT, format="json").data
    reporter.post("/api/issues/", {**SPOT, "category": "garbage", "latitude": "23.700000"}, format="json")
    ward = Authority.objects.create(name_bn="ওয়ার্ড ৭", name_en="Ward 7")
    Issue.objects.filter(pk=first["id"]).update(status="resolved", authority=ward, resolved_at=timezone.now())
    res = APIClient().get("/api/issues/transparency/?days=30")
    assert res.status_code == 200
    assert res.data["reported"] == 2 and res.data["resolved"] == 1 and res.data["resolution_rate"] == 50
    assert res.data["by_authority"][0]["name_en"] == "Ward 7" and res.data["by_authority"][0]["resolved"] == 1
    assert "Rahim" not in str(res.data) and "user_id" not in str(res.data)


@pytest.mark.django_db
def test_authority_feed_link_lists_and_resolves_its_issues(reporter, captured_events):
    admin = auth_client("admin", user_id=1)
    issue = reporter.post("/api/issues/", SPOT, format="json").data
    ward = admin.post("/api/admin/authorities/", {"name_bn": "ওয়ার্ড ৭", "name_en": "Ward 7", "categories": ["streetlight"]}, format="json").data
    assert admin.post(f"/api/admin/issues/{issue['id']}/status/", {"status": "forwarded", "authority": ward["id"]}, format="json").status_code == 200
    token = admin.post(f"/api/admin/authorities/{ward['id']}/rotate-feed/").data["feed_token"]

    office = APIClient()
    assert office.get("/api/issues/feed/not-a-token/").status_code == 404
    feed = office.get(f"/api/issues/feed/{token}/")
    assert feed["Content-Type"].startswith("text/csv")
    body = feed.content.decode("utf-8-sig")
    assert "Broken streetlight" in body and "Rahim" not in body
    done = office.post(f"/api/issues/feed/{token}/{issue['id']}/", {"status": "in_progress", "note": "Crew sent"}, format="json")
    assert done.status_code == 200 and done.data["status"] == "in_progress"
    assert office.post(f"/api/issues/feed/{token}/{issue['id']}/", {"status": "rejected"}, format="json").status_code == 400

    # rotating the link locks the old one out
    admin.post(f"/api/admin/authorities/{ward['id']}/rotate-feed/")
    assert office.get(f"/api/issues/feed/{token}/").status_code == 404
    export = admin.get("/api/admin/issues/export/")
    assert export.status_code == 200 and "Broken streetlight" in export.content.decode("utf-8-sig")


@pytest.mark.django_db
def test_issue_and_post_lists_filter_by_city(reporter, monkeypatch):
    from city_app import transparency

    monkeypatch.setattr(transparency, "city_area_ids", lambda city: [9] if city == "Khulna" else [3])
    reporter.post("/api/issues/", SPOT, format="json")  # area 3 (Dhaka)
    reporter.post("/api/issues/", {**SPOT, "area_id": 9, "area_name": "সোনাডাঙ্গা", "latitude": "22.815500", "longitude": "89.548000"}, format="json")
    titles = lambda city: [i["area_id"] for i in APIClient().get(f"/api/issues/?city={city}").data["results"]]
    assert titles("Khulna") == [9] and titles("Dhaka") == [3]
    assert len(APIClient().get("/api/issues/").data["results"]) == 2
    reporter.post("/api/community/posts/", {"area_id": 9, "area_name": "সোনাডাঙ্গা", "kind": "tip", "body": "খুলনা"}, format="json")
    reporter.post("/api/community/posts/", {"area_id": 3, "area_name": "Mirpur", "kind": "tip", "body": "ঢাকা"}, format="json")
    assert [p["body"] for p in APIClient().get("/api/community/posts/?city=Khulna").data["results"]] == ["খুলনা"]
