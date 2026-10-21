"""report-out/report.html: the ShohorSathi website page by page, focused on Khulna, with tables of the Khulna demo records.

Order: python3 scripts/report/collect.py → node scripts/report/shots.mjs → python3 scripts/report/build.py → node scripts/report/render.mjs
"""
import html
import json
import pathlib
from collections import Counter
from datetime import date

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parents[1] / "report-out"
SHOTS, IMG = OUT / "shots", OUT / "img"
IMG.mkdir(exist_ok=True)
D = json.loads((OUT / "data.json").read_text())
e = html.escape

CAT = {"garbage": ("ময়লা-আবর্জনা", "Garbage"), "streetlight": ("নষ্ট রাস্তার বাতি", "Street light"), "waterlogging": ("জলাবদ্ধতা", "Waterlogging"),
       "road_damage": ("ভাঙা রাস্তা", "Broken road"), "drainage": ("ড্রেন বন্ধ", "Blocked drain"), "mosquito": ("মশার উপদ্রব", "Mosquitoes"),
       "water_supply": ("পানি সরবরাহ", "Water supply"), "other": ("অন্যান্য", "Other")}
ISSUE_STATUS = {"reported": "Reported", "forwarded": "Forwarded to authority", "in_progress": "Work in progress", "resolved": "Resolved", "rejected": "Rejected"}
JOB_STATUS = {"open": "Waiting for a provider", "accepted": "Accepted", "on_the_way": "On the way", "working": "Working", "completed": "Completed", "cancelled": "Cancelled"}
PTYPE = {"electrician": "Electrician", "cleaner": "Cleaner", "ac_technician": "AC technician & plumber", "painter": "Painter & house shifting"}
area_bn = {a["id"]: a["name_bn"] for a in D["all_areas"]}
area_en = {a["id"]: a["name_en"] for a in D["all_areas"]}


def segments(name, width, max_ratio, max_parts, first_ratio=None):
    """Resize a full-page screenshot and cut it into page-sized JPEG pieces (the first shorter, to share a page with its caption)."""
    src = Image.open(SHOTS / f"{name}.png").convert("RGB")
    h = round(src.height * width / src.width)
    im = src.resize((width, h), Image.LANCZOS)
    step = int(width * max_ratio)
    first = int(width * (first_ratio or max_ratio))
    tops = [0] + list(range(first, h, step))
    out = []
    for i, top in enumerate(tops):
        if i >= max_parts:
            break
        piece = im.crop((0, top, width, min(h, first if i == 0 else top + step)))
        if piece.height < 80:
            break
        path = IMG / f"{name}-{i}.jpg"
        piece.save(path, "JPEG", quality=80, optimize=True, progressive=True)
        out.append(path.name)
    return out, len(tops) > max_parts


def shot(name, title, what, details=(), parts=2):
    files, cut = segments(name, 1500, 1.32, parts, first_ratio=1.0)
    lis = "".join(f"<li>{d}</li>" for d in details)
    imgs = "".join(f'<img class="shot" src="img/{f}">' for f in files)
    more = '<p class="cut">… page continues (shortened for print)</p>' if cut else ""
    return f'<section class="fig"><h3>{title}</h3><p>{what}</p>{f"<ul>{lis}</ul>" if lis else ""}{imgs}{more}</section>'


def phones(items):
    cells = []
    for name, caption in items:
        files, _ = segments(name, 520, 2.1, 1)
        cells.append(f'<figure class="phone"><img src="img/{files[0]}"><figcaption>{caption}</figcaption></figure>')
    return f'<div class="phones">{"".join(cells)}</div>'


def table(head, rows, cls=""):
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'


# ---------- Khulna data ----------
issues, orders, jobs, provs = D["issues"], D["orders"], D["jobs"], D["providers"]
kh_ids = {a["id"] for a in D["areas"]}
issue_rows = []
for i in sorted(issues, key=lambda i: (i["category"], i["area_name"])):
    auth = i["authority_name"]["bn"] if i["authority_name"] else "—"
    note = i["admin_note"] or ""
    issue_rows.append([f'<b>{e(i["title"])}</b><br><span class="muted">{e(i["description"])}</span>',
                       f'{CAT[i["category"]][0]}<br><span class="muted">{CAT[i["category"]][1]}</span>',
                       f'{e(i["area_name"])}<br><span class="muted">{area_en.get(i["area_id"], "")}</span>',
                       f'<span class="st st-{i["status"]}">{ISSUE_STATUS[i["status"]]}</span>' + (f'<br><span class="muted">{e(note)}</span>' if note else ""),
                       e(auth), f'<span class="st">▲ {i["upvote_count"]}</span>'])

order_rows = []
for o in sorted(orders, key=lambda o: o["number"]):
    if o["bookings"]:
        b = o["bookings"][0]
        what = f'{e(b["service_name"])}<br><span class="muted">{e(b.get("problem_description") or "")}</span>'
        prov = e(b.get("provider_name") or "—")
        when = f'{b["scheduled_date"]}<br><span class="muted">{e(b.get("slot_label") or b["slot"])}</span>'
        st = b["status"]
    else:
        what = "<br>".join(f'{e(it["name"])} × {it["quantity"]}' for it in o["items"])
        prov, when, st = "Shop delivery", o["created_at"][:10], o["status"]
    order_rows.append([o["number"], e(o["contact_name"]), e(o["area_name"]), what, prov, when,
                       f'<span class="st">{e(st.replace("_", " "))}</span>', f'৳{float(o["total"]):,.0f}'])

rev = {int(pid): rs for pid, rs in D["reviews"].items()}
prov_rows = []
for p in provs:
    rs = rev.get(p["id"], [])
    prov_rows.append([f'<b>{e(p["full_name"])}</b><br><span class="muted">{p["phone"]}</span>', PTYPE.get(p["provider_type"], p["provider_type"]),
                      "Female" if p["gender"] == "female" else "Male", ", ".join(e(area_bn.get(a, "")) for a in p["area_ids"] if a in kh_ids),
                      p["jobs_completed"], f'{p["rating_avg"]} ({p["rating_count"]})',
                      "<br>".join(f'{"★" * r["rating"]} {e(r["comment"])}' for r in rs) or "—"])

job_rows = [[e(j["title"]), e(j["customer_name"]), e(j["area_name"]), e(j.get("provider_name") or "—"), JOB_STATUS.get(j["status"], j["status"]),
             f'৳{float(j["amount"]):,.0f}'] for j in sorted(jobs, key=lambda j: j["status"])]

tr = {a["name_bn"]: a for a in D["transparency"]["by_authority"]}
auth_rows = []
for a in D["authorities"]:
    if "Khulna" not in a["name_en"]:
        continue
    t = tr.get(a["name_bn"], {})
    auth_rows.append([f'<b>{e(a["name_bn"])}</b><br><span class="muted">{e(a["name_en"])}</span>', ", ".join(CAT[c][0] for c in a["categories"]),
                      t.get("assigned", 0), t.get("resolved", 0), t.get("open", 0), "Yes (secret CSV link)" if a["feed_token"] else "—"])

ic, oc = Counter(i["area_id"] for i in issues), Counter(o["area_id"] for o in orders)
pc = Counter(p["area_id"] for p in D["posts"])
area_rows = []
for a in sorted(D["areas"], key=lambda a: a["name_en"]):
    kinds = sorted({CAT[i["category"]][0] for i in issues if i["area_id"] == a["id"]})
    area_rows.append([f'<b>{e(a["name_bn"])}</b> <span class="muted">{e(a["name_en"])}</span>', ic[a["id"]], ", ".join(kinds) or "—", oc[a["id"]], pc[a["id"]]])

post_rows = [[e(p["author_name"]), e(p["area_name"]), e(p["kind"]), e(p["body"])] for p in D["posts"]]
deal_rows = [[e(d["title_bn"]), e(d["service_name_bn"]), f'{d["discount_percent"]}%', f'৳{float(d["discounted_price"]):,.0f} (was ৳{float(d["base_price"]):,.0f})',
              f'{d["current_participants"]}/{d["target_participants"]}'] for d in D["deals"] if any(a in kh_ids for a in d.get("area_ids", []))]
cr_rows = [[e(c["service_type"]), e(c["customer_name"]), e(c["area_name"]), e(c["status"].replace("_", " ")),
            f'৳{float(c["quote"]["total"]):,.0f}' if c.get("quote") else "waiting for quote"] for c in D["custom_requests"]]

cat_count = Counter(i["category"] for i in issues)
status_count = Counter(i["status"] for i in issues)
S, T = D["summary"], D["transparency"]
done_jobs = sum(1 for j in jobs if j["status"] == "completed")
stats = [("Areas", len(D["areas"])), ("Providers", len(provs)), ("Customers", len({o["user_id"] for o in orders})), ("Orders", len(orders)),
         ("Jobs completed", done_jobs), ("City problem reports", len(issues)), ("Authorities", len(auth_rows)), ("Community posts", len(D["posts"]))]
tiles = "".join(f'<div class="tile"><b>{v}</b><span>{k}</span></div>' for k, v in stats)
accounts = [["01711000004 ফারহানা ইসলাম", "Customer", "সোনাডাঙ্গা"], ["01711000005 আরিফ হাসান", "Customer", "খালিশপুর"],
            ["01711000006 সুমাইয়া আক্তার", "Customer", "বয়রা"], ["01711000007 রাকিব হাসান", "Customer", "নিরালা"],
            ["01711000008 তাসলিমা খাতুন", "Customer (tenant)", "ডাকবাংলো"],
            ["01811000004 মাসুদ রানা", "Provider — electrician", "all Khulna areas"], ["01811000005 রেহানা খাতুন", "Provider — cleaner (female)", "all Khulna areas"],
            ["01811000006 সাইফুল ইসলাম", "Provider — AC & plumbing", "all Khulna areas"], ["01811000007 নাজমুল হক", "Provider — painter & shifting", "all Khulna areas"],
            ["01700000000", "Admin", "—"]]
median = T["median_days_to_resolve"]
median_text = "under 1 day" if median is not None and median < 1 else f"{median} days" if median else "—"

parts = [f"""
<section>
  <div class="brand">শহরসাথী <span>ShohorSathi</span></div>
  <h1>City problem-solving marketplace for Bangladesh</h1>
  <p class="lead">Website walkthrough — customer site, provider portal and admin panel — with a focus on <b>Khulna (খুলনা)</b></p>
  <table class="meta">
    <tr><td>Date</td><td>{date.today().strftime('%d %B %Y')}</td></tr>
    <tr><td>Source code</td><td>github.com/iftakhar-323/shohorsathi</td></tr>
    <tr><td>Stack</td><td>Django + Django REST Framework · React (Vite, TypeScript) · PostgreSQL · Celery + Redis · nginx</td></tr>
    <tr><td>Screenshots</td><td>Taken from the running system with demo data, signed in as each kind of user, city set to Khulna</td></tr>
  </table>
  <img class="cover-img" src="img/{segments('c01-home', 1500, 0.46, 1)[0][0]}">
</section>

<section class="break">
  <h2>1. What ShohorSathi is</h2>
  <p>ShohorSathi (শহরসাথী, "city companion") brings three everyday city needs into one platform:</p>
  <ul>
    <li><b>Home services</b> — book verified electricians, plumbers, AC technicians, cleaners, pest control, painters, appliance repair and
      house shifting at fixed prices, with warranty, arrival code, live tracking, reviews and an SOS button.</li>
    <li><b>Products</b> — household items (bulbs, fans, extension boards, cleaning supplies) delivered from local shops.</li>
    <li><b>City problems</b> — citizens report garbage, broken street lights, waterlogging, broken roads, blocked drains, mosquitoes,
      water-supply problems and more, with photo and map location; the platform forwards each report to the responsible office
      (City Corporation, WASA, power company) and publishes a transparency dashboard of what got fixed and how fast.</li>
  </ul>
  <p>Around these are subscriptions (weekly/monthly cleaning, meals), custom requests with quotes, an AI photo quote, a digital home
    profile with upkeep reminders, tenant/landlord approval, group deals for neighbours, seasonal offers, loyalty credit,
    a community board, provider training and insurance, and analytics (demand forecast, churn, fraud signals). The whole interface is
    in Bangla by default with an English switch.</p>
  <h3>Three web apps</h3>
  {table(["App", "For", "Main jobs"], [
      ["Customer website", "Residents of Dhaka, Chattogram, Khulna", "Find and book services, buy products, report city problems, follow orders, community, offers"],
      ["Provider portal", "Electricians, cleaners, technicians, painters …", "Accept jobs in their areas, arrival code, before/after photos, earnings and payouts, training, insurance"],
      ["Admin panel", "ShohorSathi operations team", "Verify providers, assign jobs, forward city problems to authorities, offers, analytics, safety"],
  ])}
  <h3>Architecture</h3>
  <div class="arch">
    <div class="box">Customer site<br>Provider portal<br>Admin panel<br><span>React · Vite · TypeScript</span></div>
    <div class="arrow">→</div>
    <div class="box">nginx gateway<br><span>/api · /media</span></div>
    <div class="arrow">→</div>
    <div class="box wide">14 Django REST services, each with its own PostgreSQL database:<br>
      <span>auth · catalog · order · provider · custom_request · media · subscription · payment · chat · notification · city · loyalty · b2b · analytics</span><br>
      <span>Events between services: Celery + Redis with a transactional outbox</span></div>
  </div>
  <h3>How to run it</h3>
  <pre>git clone https://github.com/iftakhar-323/shohorsathi.git && cd shohorsathi
scripts/up.sh --demo        # builds and starts the backend, loads this demo data
pnpm install && pnpm dev    # customer :5173 · provider :5174 · admin :5175</pre>
  <p class="muted">Full instructions, demo accounts and troubleshooting: SETUP.md in the repository. All demo accounts use the password <b>demo1234</b>.</p>
</section>

<section class="break">
  <h2>2. Khulna at a glance</h2>
  <p>Khulna is set up as a full city in the demo: its own areas, providers, customers, orders and city problems of every kind, handled by the
    kinds of offices that deal with them in Khulna.</p>
  <div class="tiles">{tiles}</div>
  {table(["Account (password demo1234)", "Role", "Lives / works in"], accounts, "small")}
  <h3>Areas of Khulna and what happens in each</h3>
  {table(["Area", "Problem reports", "Kinds of problems", "Orders", "Posts"], area_rows, "small")}
  <h3>City problems reported in Khulna ({len(issues)})</h3>
  <p>Every one of the 8 problem kinds appears ({", ".join(f"{CAT[c][1]} {n}" for c, n in sorted(cat_count.items()))}),
     in every state ({", ".join(f"{ISSUE_STATUS[s]} {n}" for s, n in status_count.items())}). Each report has a photo, a map pin and a
     public timeline; neighbours upvote (▲) to raise its priority.</p>
  {table(["Report", "Kind", "Area", "Status", "Sent to", "▲"], issue_rows, "small")}
  <h3>Responsible offices (authorities) for Khulna</h3>
  <p>Each office gets a secret link to download its own reports as CSV and mark them in progress or resolved, without an account.</p>
  {table(["Office", "Handles", "Assigned", "Resolved", "Open", "Feed link"], auth_rows, "small")}
  <p>Transparency dashboard for Khulna (last 90 days): <b>{T["reported"]}</b> reports, <b>{T["resolved"]}</b> resolved
     ({T["resolution_rate"]}%), <b>{T["open"]}</b> open, typical time to resolve {median_text} (the demo data is created in one go).</p>
  <h3>Service orders in Khulna ({len(orders)})</h3>
  {table(["Order", "Customer", "Area", "Service / items", "Provider", "When", "Status", "Total"], order_rows, "small")}
  <h3>Provider jobs in Khulna</h3>
  {table(["Job", "Customer", "Area", "Provider", "Status", "Amount"], job_rows, "small")}
  <h3>Khulna providers, ratings and reviews</h3>
  {table(["Provider", "Work", "Gender", "Areas covered", "Jobs done", "Rating", "Customer reviews"], prov_rows, "small")}
  <h3>Custom requests (work not in the catalog)</h3>
  {table(["Request", "Customer", "Area", "Status", "Quote"], cr_rows, "small")}
  <h3>Offers for Khulna</h3>
  {table(["Group deal", "Service", "Discount", "Deal price", "Flats joined"], deal_rows, "small")}
  <p>Seasonal package <b>“খুলনায় বর্ষার প্রস্তুতি”</b> (Khulna monsoon ready): 12% off plumbing, basin repair and mosquito fogging, shown on the
     home page with a Sundarbans river photo. Sponsored listing: ceiling-fan installation by “খুলনা ইলেকট্রিক হাউস, ডাকবাংলো”.</p>
  <h3>Community board posts from Khulna</h3>
  {table(["Author", "Area", "Type", "Post"], post_rows, "small")}
  <h3>Khulna in the analytics (last 30 days)</h3>
  {table(["Measure", "Value"], [
      ["Order value (GMV)", f'৳{float(S["gmv"]):,.0f}'], ["Revenue from completed orders", f'৳{float(S["revenue_completed"]):,.0f}'],
      ["Platform commission", f'৳{float(S["commission"]):,.0f}'], ["Orders / completed / cancelled", f'{S["orders"]} / {S["orders_completed"]} / {S["orders_cancelled"]}'],
      ["Bookings", S["bookings"]], ["Top service", e(S["top_services"][0]["title"]) if S["top_services"] else "—"],
  ], "small")}
  <p class="muted">Analytics include an 8-week synthetic booking history (customer ids #9000+) so the demand forecast, churn and fraud
     screens have something to show; every other number in this document comes from the demo records above.</p>
</section>
"""]

parts.append('<section class="break"><h2>3. Customer website (http://localhost:5173)</h2><p>City picker set to <b>খুলনা</b>. First as a visitor, then signed in as Khulna residents.</p></section>')
parts.append(shot("c01-home", "3.1 Home page", "Bangla-first landing page: search with voice input, quick service chips, the emergency panel, AI photo quote and home profile, seasonal packages with photos (the Khulna monsoon package first), neighbourhood group deals and popular services.",
                  ["“English” button switches the whole site to English", "City picker (pin icon) shows ঢাকা, চট্টগ্রাম, খুলনা", "Low-data mode (⚡) hides photos on slow connections"], parts=4))
parts.append(shot("c02-services", "3.2 Services", "All 14 services with photo, warranty, starting price and a “sponsored” label on paid placements. Filters for search, area (Khulna areas when Khulna is selected), category and sorting."))
parts.append(shot("c03-service-detail", "3.3 Booking a service — AC cleaning", "Pick a date and a two-hour slot, describe the problem, add photos, optionally ask for a female provider, then add to the cart. Shows warranty, verified providers and duration.", parts=1))
parts.append(shot("c04-shop", "3.4 Shop", "Household products from local shops with price, unit and stock; added to the same cart as services.", parts=1))
parts.append(shot("c05-subscription-plans", "3.5 Subscriptions", "Weekly or monthly cleaning (and meal) plans for 7, 15 or 30 days, with same-cleaner guarantee, before/after photos and free re-clean.", parts=1))
parts.append(shot("c06-issues-khulna", "3.6 City problems in Khulna", "Every open report in Khulna on a map and in a list, ordered by neighbours' support (▲). Filters by area, kind and status, and “near me”.",
                  ["Choosing খুলনা in the header limits the list and the map to Khulna", "Coloured status labels: reported, forwarded, in progress"], parts=3))
parts.append(shot("c07-issue-mosquito", "3.7 A report in progress — mosquitoes in Nirala", "Photo, description, location map and a public timeline: reported → forwarded to Khulna City Corporation, Health (mosquito control) → work started.", parts=1))
parts.append(shot("c08-issue-resolved", "3.8 A resolved report — open dump in Moylapota", "Resolved by KCC Conservancy with a note on what was done; everyone who reported or upvoted was notified at each step.", parts=1))
parts.append(shot("c09-issue-rejected", "3.9 A rejected report — footpath occupation in Labanchara", "Rejections always carry the reason, so the citizen knows where to go instead.", parts=1))
parts.append(shot("c10-transparency", "3.10 Transparency dashboard — Khulna", "Public, with no names or phone numbers: how many problems were reported and resolved, how fast, per office and per kind, and where most are still open."))
parts.append(shot("c11-community-khulna", "3.11 Community board — Khulna", "Neighbourhood alerts (power or water cuts), tips, questions and provider recommendations, with likes and comments."))
parts.append(shot("c12-login", "3.12 Login", "Mobile number and password. Sign-up uses an OTP by SMS or WhatsApp and asks for consent to the privacy policy.", parts=1))
parts.append(shot("c14-home-english", "3.13 The same site in English", "One click switches every label; Bangla data (names, addresses) stays as entered.", parts=1))
parts.append('<section class="break"><h3>Signed in as আরিফ হাসান (Khalishpur, Khulna)</h3></section>')
for name, title, what in [
    ("a01-home-signed-in", "3.14 Home, signed in", "Notifications bell with unread count, cart and profile menu."),
    ("a02-orders", "3.15 My orders", "Each order with number, date, service and status."),
    ("a03-order-done-reviewed", "3.16 A finished order — AC cleaning by সাইফুল", "Full timeline from order to completion, provider name, the customer's 4★ review, warranty date and a warranty-claim button."),
    ("a04-order-waiting", "3.17 An order waiting for a provider — plumber visit", "Can be rescheduled or cancelled while no provider has taken it."),
    ("a05-custom-requests", "3.18 Custom requests", "Work that is not in the catalog, quoted by the operations team."),
    ("a06-custom-request-quote", "3.19 A quote — IPS battery and wiring", "Itemised quote (labour, materials, transport, platform fee); the customer accepts, counters once or rejects."),
    ("a07-notifications", "3.20 Notifications", "Updates on orders and on every city problem the customer reported or supported."),
    ("a08-wallet-points", "3.21 Credit and points", "Points from completed orders, closed-loop credit (not cash), referral code."),
    ("a10-my-issues", "3.22 My reports", "The problems this customer reported, with their current status."),
    ("a11-ai-quote", "3.23 AI photo quote", "Describe or photograph a problem; the system suggests the right catalog service and a price range. With an Anthropic API key it asks Claude to look at the photo; here it answers from the description and says so."),
    ("a12-cart", "3.24 Cart", "Services and products together."),
    ("a13-checkout", "3.25 Checkout", "Address and Khulna area, contact, time for each service, payment (cash on delivery, bKash, Nagad, card), points, and the tenant option that asks the landlord's approval by SMS."),
    ("a14-new-issue-form", "3.26 Reporting a city problem", "Choose the kind, add at least one photo, title, description, area, landmark and a map pin; a similar open report within 50 m is offered for upvoting instead."),
]:
    parts.append(shot(name, title, what, parts=1))
parts.append('<section class="break"><h3>Signed in as সুমাইয়া আক্তার (Boyra) and তাসলিমা খাতুন (Dakbangla)</h3></section>')
for name, title, what in [
    ("s01-subscriptions-mine", "3.27 My subscriptions", "Basic cleaning plan in Boyra."),
    ("s02-subscription-detail", "3.28 Subscription detail", "Visit schedule, skip a visit (credited to the next renewal), pause, auto-renew, upgrade, cancel."),
    ("s03-home-profile", "3.29 Digital home profile", "Home health score from wiring and plumbing age, appliances and overdue upkeep; reminders recur and can be booked in one tap."),
    ("s04-order-confirmed-female-cleaner", "3.30 A confirmed booking — deep clean by রেহানা", "4-digit arrival code the provider must enter, SOS button, live location sharing with family, chat with the provider."),
    ("t02-order-painting", "3.31 Wall painting booked with নাজমুল", "Confirmed booking in Dakbangla."),
    ("t03-home-profile-tenant", "3.32 Tenant mode", "A tenant's home profile with the landlord's number: repairs above a threshold ask the landlord's approval and produce a rent-deduction receipt."),
]:
    parts.append(shot(name, title, what, parts=1))

parts.append('<section class="break"><h2>4. Provider portal (http://localhost:5174)</h2><p>Signed in as <b>সাইফুল ইসলাম</b> (AC & plumbing, all Khulna areas) and <b>রেহানা খাতুন</b> (cleaner).</p></section>')
for name, title, what in [
    ("p01-inbox", "4.1 Job inbox", "Completed jobs, this week's earnings, rating and trust score; online/offline switch."),
    ("p02-new-jobs", "4.2 New jobs in my areas", "Arif's plumber visit in Khalishpur is waiting; one tap to accept."),
    ("p03-history", "4.3 Finished jobs", "Basin repair, AC gas refill and AC cleaning, all in Khulna."),
    ("p04-job-done", "4.4 A finished job", "Customer, address, map, problem, before/after photos, timeline, and rating the customer back."),
    ("p05-earnings", "4.5 Earnings and payouts", "Per-job earning after commission, weekly payout to bKash/Nagad, instant payout for a 1.5% fee."),
    ("p07-training", "4.6 Training", "Short modules with a quiz; passing gives a badge and a verifiable certificate."),
    ("p08-insurance", "4.7 Insurance", "Micro-insurance plan (weekly premium deducted from payouts) and claims."),
    ("p09-profile", "4.8 Provider profile", "Skills, the 15 Khulna areas served, working days and hours, payout account, emergency contact for SOS."),
    ("r02-job-accepted", "4.9 রেহানা's accepted job — deep clean in Boyra", "The next step, “on the way”, shares her location with the customer; SOS is always available."),
    ("r03-training-certificate", "4.10 Training passed", "Certificate available after passing the quiz."),
]:
    parts.append(shot(name, title, what, parts=1))

parts.append('<section class="break"><h2>5. Admin panel (http://localhost:5175)</h2><p>Signed in as the operations admin.</p></section>')
for name, title, what, n in [
    ("m01-dashboard", "5.1 Dashboard", "Today's orders and value, online providers, pending verifications, open jobs, custom-request queue and jobs without a provider.", 1),
    ("m02-orders", "5.2 Orders and bookings", "All orders with customer, area, items, total and status.", 1),
    ("m03-jobs", "5.3 Jobs and assignment", "Jobs without a provider (the Khulna plumbing, fogging and kitchen-cleaning jobs), with smart provider suggestions.", 1),
    ("m04-custom-requests", "5.4 Custom requests", "Requests waiting for a quote and the most-requested kinds of work.", 1),
    ("m05-providers", "5.5 Provider verification", "Approved providers with type, areas, jobs, rating and trust score; applicants are checked with NID and photos.", 1),
    ("m06-issues", "5.6 City problems", "All reports on a map and in a table with support, authority and status; CSV export.", 2),
    ("m07-authorities", "5.7 Authorities", "Khulna City Corporation (Conservancy, Engineering, Health), Khulna WASA and WZPDCL, each with its secret CSV feed link.", 1),
    ("m08-analytics-khulna", "5.8 Analytics — Khulna", "Order value, completed revenue, commission, bookings, popular services, demand by area and a demand heat-map, filtered to Khulna.", 2),
    ("m09-forecast-khulna", "5.9 Demand forecast — Khulna", "Expected bookings per category for the next 7 days and how many providers are needed.", 1),
    ("m10-churn", "5.10 Customers at risk of leaving", "Customers who have gone quiet compared with their usual ordering gap; one click sends them a come-back note.", 1),
    ("m11-fraud", "5.11 Fraud signals", "Repeated cancellations, many accounts at one address, large first cash-on-delivery orders.", 1),
    ("m12-group-deals", "5.12 Group deals", "Khalishpur and Nirala neighbourhood deals with how many flats have joined.", 1),
    ("m13-seasonal", "5.13 Seasonal packages", "Including “খুলনায় বর্ষার প্রস্তুতি”.", 1),
    ("m14-sponsored", "5.14 Sponsored listings", "Paid placements with the fee recorded as platform income.", 1),
    ("m15-subscriptions", "5.15 Subscriptions", "Active plans, visits and revenue.", 1),
    ("m17-areas", "5.16 Areas", "Dhaka, Chattogram and the 15 Khulna areas; a new city starts by adding its areas.", 2),
    ("m18-users", "5.17 Users", "Customers, providers and admins; an account can be blocked.", 1),
    ("m20-safety", "5.18 Safety", "SOS alerts and review disputes.", 1),
    ("m22-training", "5.19 Training modules", "Modules and quizzes providers take.", 1),
    ("m24-broadcast", "5.20 Send a notification", "Bangla and English message to all or some users.", 1),
]:
    parts.append(shot(name, title, what, parts=n))

parts.append(f"""<section class="break"><h2>6. On a phone</h2><p>The customer site works at phone width (390 px) without sideways scrolling; signed in as আরিফ.</p>
{phones([("x01-mobile-home", "Home"), ("x02-mobile-issues", "Khulna city problems"), ("x03-mobile-order", "An order"), ("x04-mobile-transparency", "Transparency")])}</section>""")

parts.append("""<section class="break"><h2>7. How it was checked</h2>
<ul>
  <li><b>Backend:</b> 160 automated unit tests across the 14 services, all passing.</li>
  <li><b>End-to-end API flows:</b> nine scripts (one per development phase) run real orders, jobs, payments, city reports and analytics through the gateway.</li>
  <li><b>Browser tests:</b> 24 Playwright tests, including a tour that opens every page of the three apps and fails on any JavaScript error, failed API call or broken photo.</li>
  <li><b>From a fresh clone:</b> the setup guide was followed on a clean copy of the repository and worked first time.</li>
  <li><b>While preparing this document</b> the walkthrough found and fixed: the city picker not narrowing city problems and community posts to Khulna; the transparency dashboard not following the selected city; completed orders missing from a city's analytics; provider types and other cities' area names shown as codes in the admin panel; English labels on the home profile.</li>
  <li>All screenshots in this document were taken with no JavaScript errors and no failed requests.</li>
</ul>
<h3>Good to know</h3>
<ul>
  <li>This is demo data: people, phone numbers and orders are made up; photos are free stock images (Pexels/Unsplash).</li>
  <li>Payments use a mock gateway and SMS/WhatsApp messages are logged instead of sent; real providers (SSLCommerz, bKash, an SMS gateway) are configured for production.</li>
  <li>The 8-week analytics history behind the forecast, churn and fraud screens is synthetic.</li>
</ul></section>""")

# a section intro shares its page with the first screenshot after it
for k in range(len(parts) - 1):
    if parts[k].startswith('<section class="break"><h') and parts[k + 1].startswith('<section class="fig">'):
        parts[k + 1] = parts[k + 1].replace('<section class="fig">', '<section class="fig" style="break-before:auto">', 1)

css = (HERE / "style.css").read_text()
(OUT / "report.html").write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>ShohorSathi — website walkthrough (Khulna)</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;600;700&display=swap" rel="stylesheet">
<style>{css}</style></head><body>{''.join(parts)}</body></html>""")
print("report.html written,", len(list(IMG.glob("*.jpg"))), "images")
