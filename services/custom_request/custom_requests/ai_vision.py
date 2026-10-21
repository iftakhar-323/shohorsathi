"""Photo/description → likely problem, a catalog service to book and a price range.

With ANTHROPIC_API_KEY set, Claude looks at the uploaded photo and the description and picks one of the services
the catalog actually sells. Without a key, or if the call fails, a keyword match on the description does the same
job less precisely; `engine` on the result says which one answered.
"""
import base64
import json
import logging
import mimetypes
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from shohor_common import internal

logger = logging.getLogger(__name__)

PUBLIC_PREFIX = "/media/public/"
SEVERITIES = ["low", "medium", "high", "critical"]

# Catalog category slug → words customers use for it, and what to do while waiting for the provider.
KEYWORDS = {
    "ac": (["এসি", "ঠান্ডা", "কুলিং", "গ্যাস", "compressor", "cooling", "ac "],
           "medium", "এসির কয়েল পরিষ্কার ও গ্যাস প্রেশার চেক করতে হবে। পানি পড়লে এসি বন্ধ রাখুন।"),
    "plumbing": (["পাইপ", "পানি", "লিক", "কল", "বেসিন", "টয়লেট", "ড্রেন", "pipe", "leak", "tap", "sink", "drain"],
                 "high", "পানির মেইন লাইনের চাবি বন্ধ করে রাখুন, প্লাম্বার এসে ফিটিংস বদলাবেন।"),
    "electrical": (["সুইচ", "শর্ট", "কারেন্ট", "ফ্যান", "তার", "লাইট", "spark", "switch", "short", "fan", "wiring"],
                   "critical", "মেইন সুইচ বন্ধ রাখুন এবং নিজে হাত দেবেন না।"),
    "cleaning": (["ময়লা", "পরিষ্কার", "সোফা", "কার্পেট", "দাগ", "clean", "dirty", "stain"],
                 "low", "ক্লিনার এসে মেশিন দিয়ে গভীরভাবে পরিষ্কার করবেন।"),
    "pest-control": (["তেলাপোকা", "ইঁদুর", "পোকা", "উইপোকা", "মশা", "cockroach", "rat", "termite", "pest"],
                     "medium", "খাবার ঢেকে রাখুন; ট্রিটমেন্টের সময় শিশু ও পোষা প্রাণী সরিয়ে রাখবেন।"),
}


def catalog_services():
    """Active services as {slug, name_bn, name_en, base_price, category}; empty if the catalog is unreachable."""
    try:
        data = internal.get("catalog", "/api/services/") or {}
    except internal.ServiceUnavailable:
        return []
    return [
        {
            "slug": s["slug"],
            "name_bn": s["name_bn"],
            "name_en": s["name_en"],
            "base_price": Decimal(str(s["base_price"])),
            "category": s.get("category_slug", ""),
        }
        for s in data.get("results", [])
    ]


def _local_image(photo_url):
    """Read an uploaded public photo straight from the shared media volume (never fetch arbitrary URLs)."""
    if not photo_url.startswith(PUBLIC_PREFIX):
        return None
    root = (Path(settings.MEDIA_ROOT) / "public").resolve()
    path = (root / photo_url[len(PUBLIC_PREFIX):]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    media_type = mimetypes.guess_type(path.name)[0]
    if media_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        return None
    return media_type, base64.standard_b64encode(path.read_bytes()).decode()


def _ask_claude(photo_url, description, services):
    import anthropic

    schema = {
        "type": "object",
        "properties": {
            "issue": {"type": "string", "description": "One-line summary of the problem, in Bangla"},
            "service_slug": {"type": "string", "enum": [s["slug"] for s in services]},
            "min_price": {"type": "number"},
            "max_price": {"type": "number"},
            "confidence": {"type": "number", "description": "0 to 1"},
            "severity": {"type": "string", "enum": SEVERITIES},
            "action": {"type": "string", "description": "What the customer should do until the provider arrives, in Bangla"},
        },
        "required": ["issue", "service_slug", "min_price", "max_price", "confidence", "severity", "action"],
        "additionalProperties": False,
    }
    menu = "\n".join(f"- {s['slug']}: {s['name_en']} / {s['name_bn']}, base price ৳{s['base_price']}" for s in services)
    prompt = (
        "You help customers of ShohorSathi, a home-services marketplace in Dhaka, describe a household problem "
        "before booking. From the photo (if any) and the customer's note, say what is most likely wrong, pick the one "
        "service from this list that fixes it, and estimate a realistic price range in taka for Dhaka, starting at "
        f"the service's base price and adding likely parts or extra work:\n{menu}\n\n"
        "If the photo is unclear, lower the confidence rather than guessing. Write `issue` and `action` in Bangla.\n\n"
        f"Customer's note: {description or '(none)'}"
    )
    content = []
    if image := _local_image(photo_url):
        content.append({"type": "image", "source": {"type": "base64", "media_type": image[0], "data": image[1]}})
    content.append({"type": "text", "text": prompt})

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=30.0, max_retries=1)
    response = client.beta.messages.create(
        model=settings.AI_QUOTE_MODEL,
        max_tokens=2000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": content}],
    )
    if response.stop_reason != "end_turn":
        raise ValueError(f"Claude stopped with {response.stop_reason}")
    parsed = json.loads(next(b.text for b in response.content if b.type == "text"))
    service = next(s for s in services if s["slug"] == parsed["service_slug"])
    low = max(Decimal(str(parsed["min_price"])), service["base_price"])
    return {
        "engine": "claude",
        "category": service["category"],
        "issue": parsed["issue"][:255],
        "service_slug": service["slug"],
        "service_name_bn": service["name_bn"],
        "min_price": low.quantize(Decimal("1")),
        "max_price": max(Decimal(str(parsed["max_price"])), low).quantize(Decimal("1")),
        "confidence": Decimal(str(min(max(parsed["confidence"], 0), 1))).quantize(Decimal("0.01")),
        "severity": parsed["severity"],
        "action": parsed["action"],
    }


def _keyword_match(description, services):
    text = f" {description.lower()} "
    category = next((c for c, (words, *_) in KEYWORDS.items() if any(w in text for w in words)), None)
    service = next((s for s in services if s["category"] == category), None) if category else None
    if not service:
        service = next((s for s in services if s["slug"] == "electrician-visit"), services[0] if services else None)
        category = service["category"] if service else "general"
    severity, action = KEYWORDS[category][1:] if category in KEYWORDS else ("medium", "প্রোভাইডার এসে দেখে সঠিক খরচ জানাবেন।")
    base = service["base_price"] if service else Decimal("300")
    return {
        "engine": "keywords",
        "category": category,
        "issue": "বিবরণ থেকে আনুমানিক সমস্যা — প্রোভাইডার এসে নিশ্চিত করবেন",
        "service_slug": service["slug"] if service else "",
        "service_name_bn": service["name_bn"] if service else "হোম সার্ভিস ভিজিট",
        "min_price": base,
        "max_price": (base * Decimal("2.5")).quantize(Decimal("1")),
        "confidence": Decimal("0.50") if service and category in KEYWORDS else Decimal("0.20"),
        "severity": severity,
        "action": action,
    }


def analyze_photo_or_text(photo_url="", description=""):
    services = catalog_services()
    if settings.ANTHROPIC_API_KEY and services:
        try:
            return _ask_claude(photo_url, description, services)
        except Exception:  # any API, parsing or schema problem: answer from keywords instead of failing the customer
            logger.warning("AI quote: Claude call failed, using keyword match", exc_info=True)
    return _keyword_match(description, services)
