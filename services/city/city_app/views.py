from django.db.models import Count, Exists, OuterRef
from django.shortcuts import get_object_or_404
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from shohor_common.permissions import IsAdmin, token_role

from . import logic
from .models import Authority, Comment, Issue, IssueUpdate, IssueUpvote, Post, PostLike


class AuthoritySerializer(serializers.ModelSerializer):
    class Meta:
        model = Authority
        fields = ["id", "name_bn", "name_en", "contact_phone", "email", "categories", "area_ids", "is_active"]


class IssueUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueUpdate
        fields = ["status", "note", "created_at"]


class IssueSerializer(serializers.ModelSerializer):
    authority_name = serializers.SerializerMethodField()
    upvoted = serializers.BooleanField(read_only=True, default=False)
    distance_km = serializers.FloatField(read_only=True, default=None)
    updates = IssueUpdateSerializer(many=True, read_only=True)

    class Meta:
        model = Issue
        fields = [
            "id", "category", "title", "description", "photo_urls", "latitude", "longitude", "landmark", "area_id",
            "area_name", "status", "authority_name", "admin_note", "resolved_photo_urls", "upvote_count", "upvoted",
            "distance_km", "reporter_name", "created_at", "updated_at", "resolved_at", "updates",
        ]
        read_only_fields = ["status", "admin_note", "resolved_photo_urls", "upvote_count", "reporter_name", "resolved_at"]

    def get_authority_name(self, obj):
        return {"bn": obj.authority.name_bn, "en": obj.authority.name_en} if obj.authority else None

    def validate_photo_urls(self, value):
        if len(value) > 5:
            raise serializers.ValidationError("Up to 5 photos.")
        return value


class MapIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Issue
        fields = ["id", "category", "title", "latitude", "longitude", "status", "upvote_count"]


def uid(request):
    return request.user.id if request.user and request.user.is_authenticated else None


class IssueViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Public map and list; reporting and upvoting need a login.
    Filters: ?area= &category= &status= (comma lists) &near=lat,lng &radius_km=2 &mine=1"""

    serializer_class = IssueSerializer

    def get_permissions(self):
        return [AllowAny()] if self.action in ("list", "retrieve", "map") else [IsAuthenticated()]

    def get_queryset(self):
        qs = Issue.objects.select_related("authority").prefetch_related("updates")
        p = self.request.query_params
        if a := p.get("area"):
            qs = qs.filter(area_id=a)
        if c := p.get("category"):
            qs = qs.filter(category__in=c.split(","))
        if s := p.get("status"):
            qs = qs.filter(status__in=s.split(","))
        if p.get("mine") == "1" and uid(self.request):
            qs = qs.filter(user_id=uid(self.request))
        if uid(self.request):
            qs = qs.annotate(upvoted=Exists(IssueUpvote.objects.filter(issue=OuterRef("pk"), user_id=uid(self.request))))
        if p.get("sort") == "top":
            qs = qs.order_by("-upvote_count", "-created_at")
        return qs

    def list(self, request):
        qs = self.get_queryset()
        if nearby := request.query_params.get("near"):
            lat, lng = nearby.split(",")
            rows = logic.near(qs, lat, lng, float(request.query_params.get("radius_km", 2)))
            return Response({"count": len(rows), "next": None, "previous": None, "results": IssueSerializer(rows[:100], many=True).data})
        return super().list(request)

    def create(self, request):
        data = IssueSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            issue = logic.report(request.user.id, request.auth.get("name", ""), data.validated_data, force=request.data.get("force") is True)
        except logic.DuplicateIssue as dup:
            return Response(
                {"detail": "This looks already reported nearby. Upvote it instead?", "duplicate": IssueSerializer(dup.issue).data},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(IssueSerializer(issue).data, status=status.HTTP_201_CREATED)

    @action(detail=False)
    def map(self, request):
        qs = self.get_queryset().exclude(status=Issue.Status.REJECTED)[:1000]
        return Response(MapIssueSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"])
    def upvote(self, request, pk=None):
        issue = get_object_or_404(Issue, pk=pk)
        on = logic.toggle_upvote(issue, request.user.id)
        return Response({"upvoted": on, "upvote_count": issue.upvote_count})


class AdminIssueViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = IssueSerializer

    def get_queryset(self):
        qs = Issue.objects.select_related("authority").prefetch_related("updates").order_by("-upvote_count", "-created_at")
        p = self.request.query_params
        if s := p.get("status"):
            qs = qs.filter(status__in=s.split(","))
        if c := p.get("category"):
            qs = qs.filter(category=c)
        if a := p.get("area"):
            qs = qs.filter(area_id=a)
        return qs

    @action(detail=True, methods=["post"])
    def status(self, request, pk=None):
        issue = self.get_object()
        authority = get_object_or_404(Authority, pk=request.data["authority"]) if request.data.get("authority") else None
        logic.change_status(issue, request.data.get("status"), request.data.get("note", ""), authority, request.data.get("photos"))
        return Response(IssueSerializer(issue).data)

    @action(detail=False)
    def stats(self, request):
        qs = Issue.objects.all()
        return Response({
            "by_status": dict(qs.values_list("status").annotate(n=Count("id"))),
            "by_category": dict(qs.values_list("category").annotate(n=Count("id"))),
            "open_by_area": list(qs.exclude(status__in=["resolved", "rejected"]).values("area_id", "area_name").annotate(n=Count("id")).order_by("-n")[:20]),
        })


class AuthorityViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AuthoritySerializer
    queryset = Authority.objects.all()
    pagination_class = None


class PostSerializer(serializers.ModelSerializer):
    liked = serializers.BooleanField(read_only=True, default=False)
    mine = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ["id", "author_name", "area_id", "area_name", "kind", "body", "photo_urls", "provider_id", "provider_name",
                  "like_count", "comment_count", "liked", "mine", "created_at"]
        read_only_fields = ["author_name", "like_count", "comment_count"]

    def get_mine(self, obj):
        request = self.context.get("request")
        return bool(request and uid(request) == obj.user_id)


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ["id", "author_name", "body", "created_at"]


class PostViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Neighbourhood feed: ?area= &kind="""

    serializer_class = PostSerializer

    def get_permissions(self):
        return [AllowAny()] if self.action in ("list", "comments") and self.request.method == "GET" else [IsAuthenticated()]

    def get_queryset(self):
        qs = Post.objects.filter(is_hidden=False)
        p = self.request.query_params
        if a := p.get("area"):
            qs = qs.filter(area_id=a)
        if k := p.get("kind"):
            qs = qs.filter(kind=k)
        if uid(self.request):
            qs = qs.annotate(liked=Exists(PostLike.objects.filter(post=OuterRef("pk"), user_id=uid(self.request))))
        return qs

    def perform_create(self, serializer):
        serializer.save(user_id=self.request.user.id, author_name=self.request.auth.get("name", ""))

    def perform_destroy(self, instance):
        if instance.user_id != self.request.user.id and token_role(self.request) != "admin":
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied()
        instance.delete()

    @action(detail=True, methods=["post"])
    def like(self, request, pk=None):
        post = get_object_or_404(Post, pk=pk, is_hidden=False)
        on = logic.toggle_like(post, request.user.id)
        return Response({"liked": on, "like_count": post.like_count})

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        post = get_object_or_404(Post, pk=pk, is_hidden=False)
        if request.method == "POST":
            if not request.user.is_authenticated:
                return Response(status=status.HTTP_401_UNAUTHORIZED)
            c = logic.add_comment(post, request.user.id, request.auth.get("name", ""), request.data.get("body", ""))
            return Response(CommentSerializer(c).data, status=status.HTTP_201_CREATED)
        return Response(CommentSerializer(post.comments.all(), many=True).data)


class AdminHidePostView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        Post.objects.filter(pk=pk).update(is_hidden=True)
        return Response(status=status.HTTP_204_NO_CONTENT)
