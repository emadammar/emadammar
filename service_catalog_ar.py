# service_catalog_ar.py
# Arabic display catalog for common services (grouped by categories).
# This does NOT replace provider catalog; it only improves UI/UX for common items.

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ServiceItem:
    code: str         # provider service code (e.g., wa, tg, fb)
    ar: str           # Arabic display name
    en: str = ""      # Optional English name


# =========================
# Categories (UI)
# =========================
CATEGORIES: List[Tuple[str, str]] = [
    ("social", "تواصل وسوشيال"),
    ("bigtech", "جوجل/أبل/مايكروسوفت"),
    ("shopping", "تسوق ومتاجر"),
    ("payments", "دفع وبنوك ومحافظ"),
    ("delivery", "توصيل ومواصلات"),
    ("dating", "مواعدة"),
    ("games", "ألعاب"),
    ("email_work", "إيميل/خدمات عمل"),
    ("other", "أخرى"),
]

# =========================
# Common services per category
# =========================
CATEGORY_SERVICES: Dict[str, List[ServiceItem]] = {
    "social": [
        ServiceItem("wa", "واتساب", "WhatsApp"),
        ServiceItem("tg", "تيليغرام", "Telegram"),
        ServiceItem("fb", "فيسبوك", "Facebook"),
        ServiceItem("ig", "إنستغرام", "Instagram"),
        ServiceItem("tw", "تويتر / X", "Twitter"),
        ServiceItem("lf", "تيك توك", "TikTok"),
        ServiceItem("fu", "سناب شات", "Snapchat"),
        ServiceItem("ds", "ديسكورد", "Discord"),
        ServiceItem("vi", "فايبر", "Viber"),
        ServiceItem("me", "لاين", "LINE"),
        ServiceItem("wb", "وي تشات", "WeChat"),
        ServiceItem("bw", "سيغنال", "Signal"),
    ],
    "bigtech": [
        ServiceItem("go", "جوجل", "Google"),
        ServiceItem("wx", "أبل", "Apple"),
        ServiceItem("mm", "مايكروسوفت", "Microsoft"),
        ServiceItem("mb", "ياهو", "Yahoo"),
        ServiceItem("ya", "ياندكس", "Yandex"),
    ],
    "shopping": [
        ServiceItem("am", "أمازون", "Amazon"),
        ServiceItem("hx", "علي إكسبريس", "AliExpress"),
        ServiceItem("ep", "تيمو", "Temu"),
        ServiceItem("wr", "وولمارت", "Walmart"),
        ServiceItem("ka", "شوبي", "Shopee"),
        ServiceItem("qd", "تاوباو", "Taobao"),
    ],
    "payments": [
        ServiceItem("ts", "باي بال", "PayPal"),
        ServiceItem("jq", "بايسافكارد", "Paysafecard"),
        ServiceItem("aon", "باينانس", "Binance"),
        ServiceItem("re", "كوينبيس", "Coinbase"),
        ServiceItem("bo", "وايز", "Wise"),
        ServiceItem("ij", "ريفولت", "Revolut"),
    ],
    "delivery": [
        ServiceItem("ub", "أوبر", "Uber"),
        ServiceItem("tu", "ليفت", "Lyft"),
        ServiceItem("xk", "ديدي", "DiDi"),
        ServiceItem("ac", "دورداش", "DoorDash"),
        ServiceItem("aq", "جلوبو", "Glovo"),
        ServiceItem("rr", "وولت", "Wolt"),
        ServiceItem("ul", "جيتير", "Getir"),
    ],
    "dating": [
        ServiceItem("oi", "تيندر", "Tinder"),
        ServiceItem("mo", "بامبل", "Bumble"),
        ServiceItem("vz", "هينج", "Hinge"),
        ServiceItem("df", "هابّن", "Happn"),
    ],
    "games": [
        ServiceItem("mt", "ستيم", "Steam"),
        ServiceItem("hb", "تويتش", "Twitch"),
        ServiceItem("bz", "بليزارد", "Blizzard"),
        ServiceItem("ah", "إسكاب فروم تاركوف", "Escape From Tarkov"),
        ServiceItem("ahb", "يوبيسوفت", "Ubisoft"),
    ],
    "email_work": [
        ServiceItem("pm", "AOL", "AOL"),
        ServiceItem("dp", "بروتون ميل", "ProtonMail"),
        ServiceItem("tn", "لينكدإن", "LinkedIn"),
        ServiceItem("cn", "فايفر", "Fiverr"),
        ServiceItem("gr", "أستروباي", "Astropay"),
    ],
    "other": [
        # Keep "other" small; users can use Search for everything else.
        ServiceItem("ee", "توایلیو", "Twilio"),
        ServiceItem("vk", "VK", "VK"),
    ],
}

# Build quick lookup: code -> ServiceItem
_CODE_MAP: Dict[str, ServiceItem] = {}
for _cat, _items in CATEGORY_SERVICES.items():
    for _it in _items:
        _CODE_MAP[_it.code] = _it


def get_categories() -> List[Tuple[str, str]]:
    """Return list of (category_key, arabic_title)."""
    return CATEGORIES.copy()


def get_common_services(category_key: str) -> List[ServiceItem]:
    """Return common services list for a category."""
    return CATEGORY_SERVICES.get(category_key, []).copy()


def translate_code(code: str) -> Optional[ServiceItem]:
    """Return ServiceItem if known; else None."""
    return _CODE_MAP.get((code or "").strip())


def format_service_label(code: str) -> str:
    """
    UI label: 'واتساب — (wa)' if translated
    else: 'wa' only (caller can append provider name if needed).
    """
    it = translate_code(code)
    if it:
        return f"{it.ar} — ({it.code})"
    return f"{code}"