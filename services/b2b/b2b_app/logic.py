import calendar
from datetime import date, timedelta
from decimal import Decimal
from html import escape

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from shohor_common import events, internal

from .models import Contract, ContractVisit, Invoice, InvoiceLine, Membership, Organization

V = ContractVisit.Status


def membership(org, user_id):
    return org.members.filter(user_id=user_id).first()


def require_admin(org, user_id):
    m = membership(org, user_id)
    if m is None or m.role != Membership.Role.ADMIN:
        raise PermissionDenied("Only the organization's admins can do this.")


@transaction.atomic
def create_org(user, data):
    org = Organization.objects.create(created_by=user["id"], **data)
    Membership.objects.create(organization=org, user_id=user["id"], name=user["name"], phone=user["phone"], role=Membership.Role.ADMIN)
    return org


def add_member(org, phone, role):
    user = internal.get("auth", f"/api/internal/users/by-phone/{phone}/")
    if user is None:
        raise NotFound("No ShohorSathi account with this number. Ask them to sign up first.")
    m, _ = Membership.objects.update_or_create(organization=org, user_id=user["id"], defaults={"name": user["full_name"], "phone": phone, "role": role})
    return m


def month_visit_dates(start, weekday, per_month, months):
    """Spread `per_month` visits over each month on the preferred weekday."""
    dates = []
    first = date(start.year, start.month, 1)
    for m in range(months):
        y, mo = first.year + (first.month - 1 + m) // 12, (first.month - 1 + m) % 12 + 1
        # Only days from the start date on, so a contract starting mid-month still gets its visits that month.
        days = [date(y, mo, d) for d in range(1, calendar.monthrange(y, mo)[1] + 1) if date(y, mo, d).weekday() == weekday and date(y, mo, d) >= start]
        step = max(len(days) // max(per_month, 1), 1)
        dates += days[::step][:per_month]
    return dates


@transaction.atomic
def create_contract(org, data):
    if org.status != Organization.Status.APPROVED:
        raise ValidationError({"organization": "Approve the organization first."})
    contract = Contract.objects.create(organization=org, **data)
    months = (contract.end_date.year - contract.start_date.year) * 12 + contract.end_date.month - contract.start_date.month + 1
    ContractVisit.objects.bulk_create([
        ContractVisit(contract=contract, date=d, slot=contract.slot)
        for d in month_visit_dates(contract.start_date, contract.preferred_weekday, contract.visits_per_month, months)
        if d <= contract.end_date
    ])
    return contract


def dispatch_tomorrow():
    tomorrow = timezone.localdate() + timedelta(days=1)
    n = 0
    for v in ContractVisit.objects.select_related("contract__organization").filter(date=tomorrow, status=V.SCHEDULED, contract__status=Contract.Status.ACTIVE):
        org = v.contract.organization
        with transaction.atomic():
            events.publish("b2b.visit_due", {
                "visit_id": v.id, "user_id": org.created_by, "title": f"{org.name}: {v.contract.title}",
                "category_slug": v.contract.category_slug, "area_id": org.area_id, "area_name": org.area_name,
                "address_line": org.address_line, "customer_name": org.contact_name, "customer_phone": org.contact_phone,
                "scheduled_date": v.date.isoformat(), "slot": v.slot, "amount": "0", "description": v.contract.description,
            })
            v.status = V.DISPATCHED
            v.save(update_fields=["status"])
        n += 1
    return n


JOB_TO_VISIT = {"on_the_way": V.IN_PROGRESS, "working": V.IN_PROGRESS, "completed": V.COMPLETED, "cancelled": V.CANCELLED}


def apply_job_status(payload):
    if payload.get("source") != "b2b_visit":
        return
    new = JOB_TO_VISIT.get(payload["status"])
    fields = {"provider_name": payload.get("provider_name", "")}
    if new:
        fields["status"] = new
    ContractVisit.objects.filter(pk=payload["source_id"]).exclude(status=V.COMPLETED).update(**fields)


@transaction.atomic
def generate_invoice(org, year, month):
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    invoice, created = Invoice.objects.get_or_create(organization=org, period_start=start, defaults={"period_end": end})
    if not created:
        if invoice.status == Invoice.Status.PAID:
            raise ValidationError({"invoice": "This month's invoice is already paid."})
        invoice.lines.all().delete()
    lines = []
    for c in org.contracts.filter(start_date__lte=end, end_date__gte=start):
        done = c.visits.filter(date__range=(start, end), status=V.COMPLETED).count()
        lines.append(InvoiceLine(invoice=invoice, description=f"{c.title} — monthly fee ({done} visits done)", amount=c.monthly_fee))
    for o in internal.get("order", "/api/internal/orders/", organization_id=org.id, **{"from": start.isoformat(), "to": end.isoformat()}) or []:
        lines.append(InvoiceLine(invoice=invoice, description=f"Order {o['number']} ({o['date']}): {', '.join(o['items'])[:180]}", amount=Decimal(o["total"])))
    InvoiceLine.objects.bulk_create(lines)
    invoice.total = sum((line.amount for line in lines), Decimal("0"))
    invoice.save(update_fields=["total"])
    events.publish("b2b.invoice_issued", {"user_id": org.created_by, "organization_id": org.id, "invoice_id": invoice.id,
                                          "number": invoice.number, "total": str(invoice.total)})
    return invoice


def monthly_invoices():
    """On the 1st: invoice every approved organization for the previous month."""
    last = timezone.localdate().replace(day=1) - timedelta(days=1)
    n = 0
    for org in Organization.objects.filter(status=Organization.Status.APPROVED):
        if org.contracts.exists() or internal.get("order", "/api/internal/orders/", organization_id=org.id, **{"from": last.replace(day=1).isoformat(), "to": last.isoformat()}):
            generate_invoice(org, last.year, last.month)
            n += 1
    return n


def invoice_html(invoice):
    org = invoice.organization
    rows = "".join(f"<tr><td>{escape(line.description)}</td><td class='n'>৳ {line.amount:,.2f}</td></tr>" for line in invoice.lines.all())
    paid = f"<p class='paid'>PAID {invoice.paid_at:%d %b %Y} · {escape(invoice.payment_reference)}</p>" if invoice.status == "paid" else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{invoice.number}</title>
<style>body{{font-family:system-ui,sans-serif;color:#12201a;max-width:760px;margin:40px auto;padding:0 16px}}
h1{{margin:0;color:#17784a}}table{{width:100%;border-collapse:collapse;margin-top:24px}}td,th{{border-bottom:1px solid #dce5df;padding:10px;text-align:left}}
.n{{text-align:right}}.total td{{font-weight:700;font-size:18px}}.paid{{color:#17784a;font-weight:700}}@media print{{button{{display:none}}}}</style></head>
<body><h1>ShohorSathi</h1><p>Invoice / Receipt <strong>{invoice.number}</strong><br>Period {invoice.period_start:%d %b %Y} – {invoice.period_end:%d %b %Y}</p>
<p><strong>{escape(org.name)}</strong><br>{escape(org.address_line)}, {escape(org.area_name)}<br>{escape(org.contact_name)} · {escape(org.contact_phone)}</p>
<table><tr><th>Description</th><th class="n">Amount</th></tr>{rows}<tr class="total"><td>Total</td><td class="n">৳ {invoice.total:,.2f}</td></tr></table>
{paid}<button onclick="print()">Print / Save as PDF</button></body></html>"""
