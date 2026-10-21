from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView
from shohor_common.internal import IsInternal
from shohor_common.permissions import IsAdmin, token_role

from . import logic
from .models import Contract, ContractVisit, Invoice, InvoiceLine, Membership, Organization


class OrgSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "kind", "contact_name", "contact_phone", "billing_email", "address_line", "area_id", "area_name", "units", "status", "created_at"]
        read_only_fields = ["status", "created_at"]


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ["id", "user_id", "name", "phone", "role"]


class VisitSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractVisit
        fields = ["id", "date", "slot", "status", "provider_name"]


class ContractSerializer(serializers.ModelSerializer):
    upcoming = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = ["id", "title", "description", "category_slug", "visits_per_month", "preferred_weekday", "slot", "monthly_fee", "start_date", "end_date", "status", "upcoming"]
        read_only_fields = ["status"]

    def get_upcoming(self, obj):
        return VisitSerializer(obj.visits.filter(date__gte=timezone.localdate())[:4], many=True).data


class LineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = ["description", "amount"]


class InvoiceSerializer(serializers.ModelSerializer):
    number = serializers.CharField(read_only=True)
    lines = LineSerializer(many=True, read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = Invoice
        fields = ["id", "number", "organization", "organization_name", "period_start", "period_end", "total", "status", "paid_at", "payment_reference", "lines", "created_at"]


def me(request):
    return {"id": request.user.id, "name": request.auth.get("name", ""), "phone": request.auth.get("phone", "")}


def my_org(request, pk):
    org = get_object_or_404(Organization, pk=pk)
    if token_role(request) != "admin" and not logic.membership(org, request.user.id):
        raise NotFound()
    return org


class OrgsView(APIView):
    def get(self, request):
        orgs = Organization.objects.filter(members__user_id=request.user.id)
        return Response(OrgSerializer(orgs, many=True).data)

    def post(self, request):
        data = OrgSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(OrgSerializer(logic.create_org(me(request), data.validated_data)).data, status=status.HTTP_201_CREATED)


class OrgDetailView(APIView):
    """Corporate dashboard."""

    def get(self, request, pk):
        org = my_org(request, pk)
        month_start = timezone.localdate().replace(day=1)
        return Response({
            **OrgSerializer(org).data,
            "my_role": getattr(logic.membership(org, request.user.id), "role", "admin"),
            "members": MemberSerializer(org.members.all(), many=True).data,
            "contracts": ContractSerializer(org.contracts.all(), many=True).data,
            "stats": {
                "members": org.members.count(),
                "active_contracts": org.contracts.filter(status="active").count(),
                "visits_this_month": ContractVisit.objects.filter(contract__organization=org, date__gte=month_start).count(),
                "unpaid_total": str(org.invoices.filter(status="issued").aggregate(s=Sum("total"))["s"] or 0),
                "paid_this_year": str(org.invoices.filter(status="paid", period_start__year=month_start.year).aggregate(s=Sum("total"))["s"] or 0),
            },
        })


class MembersView(APIView):
    def post(self, request, pk):
        org = my_org(request, pk)
        logic.require_admin(org, request.user.id)
        m = logic.add_member(org, request.data.get("phone", ""), request.data.get("role", "member"))
        return Response(MemberSerializer(m).data, status=status.HTTP_201_CREATED)

    def delete(self, request, pk):
        org = my_org(request, pk)
        logic.require_admin(org, request.user.id)
        org.members.filter(user_id=request.query_params.get("user_id")).exclude(user_id=request.user.id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvoicesView(APIView):
    def get(self, request, pk):
        return Response(InvoiceSerializer(my_org(request, pk).invoices.prefetch_related("lines"), many=True).data)


class InvoicePrintView(APIView):
    def get(self, request, pk):
        invoice = get_object_or_404(Invoice.objects.select_related("organization"), pk=pk)
        my_org(request, invoice.organization_id)
        return HttpResponse(logic.invoice_html(invoice))


class InternalMembershipView(APIView):
    permission_classes = [IsInternal]
    authentication_classes = []

    def post(self, request):
        ok = Membership.objects.filter(
            organization_id=request.data.get("organization_id"), user_id=request.data.get("user_id"), organization__status="approved"
        ).exists()
        return Response({"ok": ok})


# ---- admin -------------------------------------------------------------------------------------

class AdminOrgsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        qs = Organization.objects.all()
        if s := request.query_params.get("status"):
            qs = qs.filter(status=s)
        return Response(OrgSerializer(qs, many=True).data)


class AdminOrgActionView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, pk, action):
        org = get_object_or_404(Organization, pk=pk)
        if action in ("approve", "reject"):
            org.status = "approved" if action == "approve" else "rejected"
            org.save(update_fields=["status"])
            return Response(OrgSerializer(org).data)
        if action == "contracts":
            data = ContractSerializer(data=request.data)
            data.is_valid(raise_exception=True)
            return Response(ContractSerializer(logic.create_contract(org, data.validated_data)).data, status=status.HTTP_201_CREATED)
        if action == "invoice":
            year, month = map(int, request.data.get("period", timezone.localdate().strftime("%Y-%m")).split("-"))
            return Response(InvoiceSerializer(logic.generate_invoice(org, year, month)).data, status=status.HTTP_201_CREATED)
        raise NotFound()


class AdminInvoicesView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        qs = Invoice.objects.select_related("organization").prefetch_related("lines")
        if s := request.query_params.get("status"):
            qs = qs.filter(status=s)
        return Response(InvoiceSerializer(qs[:200], many=True).data)


class AdminInvoicePaidView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        invoice.status, invoice.paid_at = Invoice.Status.PAID, timezone.now()
        invoice.payment_reference = request.data.get("reference", "")
        invoice.save()
        return Response(InvoiceSerializer(invoice).data)
