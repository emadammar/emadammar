# tempmail/email_engine.py
# محرك الإيميل المؤقت (mail.tm) بدون TeleBot
# يعتمد على tempmail/utils.py لإنشاء الإيميل (Generate_Email) وإدارة Accounts/
# ويستخدم mail.tm API مباشرة لجلب نص الرسائل (text/html) بشكل موثوق
# + إصلاح html التي تأتي كـ list
# + استخراج روابط التفعيل من href
# + استخراج OTP من النص

import os
import re
from typing import Optional, Dict, Any, List

import requests

from . import utils  # tempmail/utils.py

MAILTM_BASE = "https://api.mail.tm"

_TAG_RE = re.compile(r"<[^>]+>", re.IGNORECASE)


def ensure_user_dirs(user_id: int) -> None:
    base = os.path.join("Accounts", str(user_id), "mails")
    os.makedirs(base, exist_ok=True)


def _user_mail_dir(user_id: int) -> str:
    return os.path.join("Accounts", str(user_id), "mails")


def _read_kv_file(path: str) -> Dict[str, str]:
    data: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = (line or "").strip()
                if not line or ":" not in line:
                    continue
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip()
    except Exception:
        return {}
    return data


def get_latest_account_file(user_id: int) -> Optional[str]:
    d = _user_mail_dir(user_id)
    if not os.path.isdir(d):
        return None
    files = []
    for name in os.listdir(d):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            files.append(p)
    if not files:
        return None
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files[0]


def get_latest_email_info(user_id: int) -> Optional[Dict[str, Any]]:
    """
    يرجع آخر ايميل محفوظ في Accounts/<uid>/mails/
    """
    fpath = get_latest_account_file(user_id)
    if not fpath:
        return None

    kv = _read_kv_file(fpath)
    token = (kv.get("account_token", "") or "").strip()
    created = (kv.get("account_creat", "") or "").strip()

    # عادة اسم الملف هو الايميل نفسه
    email = (os.path.basename(fpath) or "").strip()

    if not email or "@" not in email or not token:
        # fallback
        local = (kv.get("account_addrs", "") or "").strip()
        domain = (kv.get("account_mail_name", "") or "").strip()
        if local and domain:
            email = f"{local}@{domain}"
        if not email or not token:
            return None

    return {"email": email, "token": token, "created_at": created, "file": fpath}


def create_email_from_utils(message_obj) -> Dict[str, Any]:
    """
    ينشئ ايميل جديد باستخدام Generate_Email من utils.py
    ثم يقرأ آخر ايميل/توكن من Accounts
    """
    user_id = message_obj.from_user.id
    ensure_user_dirs(user_id)

    # Generate_Email يكتب ملفات Accounts تلقائياً
    _ = utils.Generate_Email(message_obj)

    info = get_latest_email_info(user_id)
    if not info:
        raise RuntimeError("FAILED_CREATE_EMAIL")
    return info


def _html_to_text(html: str) -> str:
    if not html:
        return ""

    # إزالة script/style
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)

    # سطور جديدة
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</p\s*>", "\n", html)
    html = re.sub(r"(?i)</div\s*>", "\n", html)
    html = re.sub(r"(?i)</tr\s*>", "\n", html)

    # حذف الوسوم
    text = _TAG_RE.sub(" ", html)

    # تنظيف المسافات
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


def _normalize_html_field(html_field) -> str:
    """
    mail.tm قد يرجّع html كـ list بدل string
    """
    if html_field is None:
        return ""
    if isinstance(html_field, list):
        # اجمع الأجزاء
        parts = []
        for x in html_field:
            if x is None:
                continue
            parts.append(str(x))
        return "\n".join(parts)
    return str(html_field)


def _extract_links_from_html(html: str, max_links: int = 5) -> List[str]:
    if not html:
        return []
    links = re.findall(r'href\s*=\s*["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
    cleaned = []
    for u in links:
        u = (u or "").strip()
        if not u:
            continue
        if u.startswith("http://") or u.startswith("https://"):
            if u not in cleaned:
                cleaned.append(u)
        if len(cleaned) >= max_links:
            break
    return cleaned


def _get_json(path: str, token: str, timeout: int = 20) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(MAILTM_BASE + path, headers=headers, timeout=timeout)
    if r.status_code == 401:
        raise RuntimeError("TOKEN_INVALID")
    r.raise_for_status()
    return r.json()


def fetch_latest_messages(token: str, limit: int = 2) -> List[str]:
    """
    يجلب آخر N رسائل كنص جاهز للعرض (From + Subject + Body)
    + يضيف روابط التفعيل إن وجدت
    """
    data = _get_json("/messages?page=1", token)
    items = data.get("hydra:member", []) if isinstance(data, dict) else []
    if not items:
        return []

    out: List[str] = []
    lim = max(1, int(limit))

    for item in items[:lim]:
        msg_id = item.get("id")
        from_obj = item.get("from") or {}
        sender = ((from_obj.get("name") or "") + " " + (from_obj.get("address") or "")).strip()
        subject = (item.get("subject") or "").strip()
        intro = (item.get("intro") or "").strip()

        body = intro
        links: List[str] = []

        if msg_id:
            full = _get_json(f"/messages/{msg_id}", token)

            body_text_raw = full.get("text")
            body_html_raw = full.get("html")

            body_text = str(body_text_raw).strip() if body_text_raw is not None else ""
            body_html = _normalize_html_field(body_html_raw).strip()

            # روابط التفعيل من HTML
            links = _extract_links_from_html(body_html)

            if body_text:
                body = body_text
            elif body_html:
                body = _html_to_text(body_html)
            else:
                body = intro

            # sender/subject من full إن توفر
            ffrom = full.get("from") or from_obj
            sender2 = (((ffrom.get("name") or "") + " " + (ffrom.get("address") or "")).strip())
            if sender2:
                sender = sender2
            subj2 = (full.get("subject") or "").strip()
            if subj2:
                subject = subj2

        links_block = ""
        if links:
            links_block = "\n\nروابط التفعيل:\n" + "\n".join(links)

        msg = f"From: {sender}\nSubject: {subject}\n\n{body}{links_block}".strip()
        out.append(msg)

    return out


def extract_otp_code(text: str) -> str:
    """
    استخراج كود OTP (أرقام 4 إلى 10)
    """
    m = re.search(r"\b(\d{4,10})\b", text or "")
    return m.group(1) if m else ""


def extract_first_link(text: str) -> str:
    """
    استخراج أول رابط من النص (ينفع إذا الموقع يرسل رابط تفعيل بدل كود)
    """
    m = re.search(r"(https?://\S+)", text or "")
    return m.group(1).strip() if m else ""