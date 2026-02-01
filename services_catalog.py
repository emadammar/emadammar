# services_catalog.py
# قائمة الخدمات + بحث موحد (متوافق 100% مع Pydroid3 + Termux)
# ملاحظة: يمكن لاحقاً نقلها لقاعدة البيانات، لكن الآن نخليها ثابتة وسهلة.

from typing import List, Dict, Any

# fuzzywuzzy قد يكون ثقيل أحياناً على الهاتف بدون python-Levenshtein
# لكنه يعمل. سنستخدمه بشكل بسيط.
from fuzzywuzzy import fuzz


# ====== Services (عادي) ======
SERVICE_MAPPINGS: List[Dict[str, Any]] = [
    {"name": "telegram", "code": "tg", "price": 1.0},
    {"name": "tiktok",   "code": "tk", "price": 2.0},
    {"name": "google",   "code": "gl", "price": 2.0},
]

# ====== Services (UK) ======
SERVICE_MAPPINGS_UK: List[Dict[str, Any]] = [
    {"name": "Open AI",  "code": "dr", "price": 4.0},
    {"name": "تيك توك",  "code": "tk", "price": 4.0},
]


def search_services(prefix: str, uk: bool = False, threshold: int = 80, limit: int = 10) -> List[Dict[str, Any]]:
    """
    بحث عن خدمات مطابقة بشكل تقريبي (fuzzy).
    prefix: ما يكتبه المستخدم (حرفين/3)
    threshold: نسبة التطابق (80 مناسب)
    """
    prefix = (prefix or "").strip().lower()
    if not prefix:
        return []

    services = SERVICE_MAPPINGS_UK if uk else SERVICE_MAPPINGS

    matches = []
    for s in services:
        name = str(s["name"]).lower()
        score = fuzz.partial_ratio(name, prefix)
        if score >= threshold:
            matches.append((score, s))

    # الأعلى تطابقاً أولاً
    matches.sort(key=lambda x: x[0], reverse=True)
    return [m[1] for m in matches[:limit]]


def get_service_by_name(name: str, uk: bool = False) -> Dict[str, Any] | None:
    name = (name or "").strip()
    services = SERVICE_MAPPINGS_UK if uk else SERVICE_MAPPINGS
    for s in services:
        if s["name"] == name:
            return s
    return None