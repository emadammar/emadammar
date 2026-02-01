# handlers_accounts.py
# إدارة وبيع حسابات التواصل:
# - الأدمن: إضافة حساب (نوع + ايميل + يوزر + باسورد + سعر)
# - المستخدم: شراء حساب حسب النوع بسعر كل حساب
# - عربي بالكامل (العرض بالعربي، والتخزين platform بالانجليزي)

from telebot.types import Message, ReplyKeyboardMarkup, KeyboardButton
import time

import db
from config import ADMIN_USER_ID

BTN_BACK = "رجوع"
BTN_CANCEL = "إلغاء"
BTN_CONFIRM_SAVE = "حفظ"
BTN_CONFIRM_BUY = "شراء"

# ما يظهر للمستخدم
ACCOUNT_TYPES_AR = ["فيسبوك", "إنستغرام", "تويتر"]

# تحويل الاسم العربي إلى platform داخلي
AR_TO_PLATFORM = {
    "فيسبوك": "facebook",
    "إنستغرام": "instagram",
    "تويتر": "twitter",
}

PLATFORM_TO_AR = {v: k for k, v in AR_TO_PLATFORM.items()}


def _kb(*rows):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for r in rows:
        if isinstance(r, (list, tuple)):
            for b in r:
                kb.add(KeyboardButton(str(b)))
        else:
            kb.add(KeyboardButton(str(r)))
    return kb


def register_accounts_handlers(bot):

    # =========================
    # Admin: Add account
    # =========================
    @bot.message_handler(func=lambda m: (m.text or "").strip() == "إضافة حساب")
    def admin_add_account(m: Message):
        if m.from_user.id != ADMIN_USER_ID:
            bot.send_message(m.chat.id, "هذا الأمر للأدمن فقط.")
            return

        kb = _kb(ACCOUNT_TYPES_AR, [BTN_CANCEL])
        bot.send_message(m.chat.id, "اختر نوع الحساب لإضافته:", reply_markup=kb)
        bot.register_next_step_handler(m, admin_step_type)

    def admin_step_type(m: Message):
        if m.from_user.id != ADMIN_USER_ID:
            bot.send_message(m.chat.id, "هذا الأمر للأدمن فقط.")
            return

        text = (m.text or "").strip()
        if text == BTN_CANCEL:
            bot.send_message(m.chat.id, "تم الإلغاء.")
            return

        if text not in ACCOUNT_TYPES_AR:
            bot.send_message(m.chat.id, "اختر نوعاً صحيحاً من الأزرار.")
            kb = _kb(ACCOUNT_TYPES_AR, [BTN_CANCEL])
            bot.send_message(m.chat.id, "اختر نوع الحساب:", reply_markup=kb)
            bot.register_next_step_handler(m, admin_step_type)
            return

        ctx = {"type_ar": text, "platform": AR_TO_PLATFORM[text]}
        bot.send_message(m.chat.id, "اكتب الإيميل (أو اكتب - إذا لا يوجد):", reply_markup=_kb([BTN_CANCEL]))
        bot.register_next_step_handler(m, admin_step_email, ctx)

    def admin_step_email(m: Message, ctx: dict):
        text = (m.text or "").strip()
        if text == BTN_CANCEL:
            bot.send_message(m.chat.id, "تم الإلغاء.")
            return

        ctx["email"] = "" if text == "-" else text
        bot.send_message(m.chat.id, "اكتب اليوزر (اسم المستخدم):", reply_markup=_kb([BTN_CANCEL]))
        bot.register_next_step_handler(m, admin_step_username, ctx)

    def admin_step_username(m: Message, ctx: dict):
        text = (m.text or "").strip()
        if text == BTN_CANCEL:
            bot.send_message(m.chat.id, "تم الإلغاء.")
            return

        ctx["username"] = text
        bot.send_message(m.chat.id, "اكتب كلمة المرور:", reply_markup=_kb([BTN_CANCEL]))
        bot.register_next_step_handler(m, admin_step_password, ctx)

    def admin_step_password(m: Message, ctx: dict):
        text = (m.text or "").strip()
        if text == BTN_CANCEL:
            bot.send_message(m.chat.id, "تم الإلغاء.")
            return

        ctx["password"] = text
        bot.send_message(m.chat.id, "اكتب السعر بالنقاط (رقم فقط):", reply_markup=_kb([BTN_CANCEL]))
        bot.register_next_step_handler(m, admin_step_price, ctx)

    def admin_step_price(m: Message, ctx: dict):
        text = (m.text or "").strip()
        if text == BTN_CANCEL:
            bot.send_message(m.chat.id, "تم الإلغاء.")
            return

        try:
            price = float(text)
            if price <= 0:
                raise ValueError()
        except Exception:
            bot.send_message(m.chat.id, "السعر غير صحيح. اكتب رقم صحيح أكبر من 0.")
            bot.send_message(m.chat.id, "اكتب السعر بالنقاط:", reply_markup=_kb([BTN_CANCEL]))
            bot.register_next_step_handler(m, admin_step_price, ctx)
            return

        ctx["price"] = price

        summary = (
            "تأكيد حفظ الحساب:\n\n"
            f"النوع: {ctx['type_ar']}\n"
            f"الإيميل: {ctx['email'] or '-'}\n"
            f"اليوزر: {ctx['username']}\n"
            f"الباسورد: {ctx['password']}\n"
            f"السعر: {ctx['price']} نقطة\n"
        )
        kb = _kb([BTN_CONFIRM_SAVE, BTN_CANCEL])
        bot.send_message(m.chat.id, summary, reply_markup=kb)
        bot.register_next_step_handler(m, admin_step_confirm_save, ctx)

    def admin_step_confirm_save(m: Message, ctx: dict):
        text = (m.text or "").strip()
        if text == BTN_CANCEL:
            bot.send_message(m.chat.id, "تم الإلغاء.")
            return

        if text != BTN_CONFIRM_SAVE:
            bot.send_message(m.chat.id, "اختر (حفظ) أو (إلغاء).")
            kb = _kb([BTN_CONFIRM_SAVE, BTN_CANCEL])
            bot.send_message(m.chat.id, "تأكيد:", reply_markup=kb)
            bot.register_next_step_handler(m, admin_step_confirm_save, ctx)
            return

        # مطابق لـ db.py الجديد
        db.add_account(
            platform=ctx["platform"],
            email=ctx["email"],
            username=ctx["username"],
            password=ctx["password"],
            price=ctx["price"],
            created_at=int(time.time()),
            added_by=m.from_user.id,
        )
        bot.send_message(m.chat.id, "تمت إضافة الحساب بنجاح.")

    # =========================
    # User: Buy account (three types)
    # =========================
    @bot.message_handler(func=lambda m: (m.text or "").strip() in ACCOUNT_TYPES_AR)
    def user_choose_account_type(m: Message):
        type_ar = (m.text or "").strip()
        user_id = m.from_user.id

        platform = AR_TO_PLATFORM.get(type_ar)
        if not platform:
            bot.send_message(m.chat.id, "نوع غير معروف.")
            return

        acc = db.peek_account(platform)
        if not acc:
            bot.send_message(m.chat.id, "لا يوجد حسابات متاحة حالياً لهذا النوع. حاول لاحقاً.")
            return

        price = float(acc.get("price", 0))
        bal = db.get_balance(user_id)

        if bal != -1 and bal < price:
            bot.send_message(m.chat.id, f"رصيدك غير كافٍ. السعر: {price} نقطة.")
            return

        kb = _kb([BTN_CONFIRM_BUY, BTN_CANCEL])
        bot.send_message(
            m.chat.id,
            f"النوع: {type_ar}\nالسعر: {price} نقطة\n\nهل تريد الشراء؟",
            reply_markup=kb
        )
        bot.register_next_step_handler(m, user_confirm_buy, platform)

    def user_confirm_buy(m: Message, platform: str):
        text = (m.text or "").strip()
        user_id = m.from_user.id

        if text == BTN_CANCEL:
            bot.send_message(m.chat.id, "تم الإلغاء.")
            return

        if text != BTN_CONFIRM_BUY:
            bot.send_message(m.chat.id, "اختر (شراء) أو (إلغاء).")
            kb = _kb([BTN_CONFIRM_BUY, BTN_CANCEL])
            bot.send_message(m.chat.id, "تأكيد:", reply_markup=kb)
            bot.register_next_step_handler(m, user_confirm_buy, platform)
            return

        acc = db.pop_account(platform)
        if not acc:
            bot.send_message(m.chat.id, "انتهى المخزون الآن. حاول لاحقاً.")
            return

        price = float(acc.get("price", 0))
        bal = db.get_balance(user_id)

        # تحقق احتياطي
        if bal != -1 and bal < price:
            # رجّع الحساب للمخزون (حتى لا يضيع)
            db.add_account(
                platform=platform,
                email=acc.get("email") or "",
                username=acc.get("username") or "",
                password=acc.get("password") or "",
                price=price,
                created_at=int(time.time()),
                added_by=int(acc.get("added_by", 0) or 0),
            )
            bot.send_message(m.chat.id, "رصيدك غير كافٍ الآن.")
            return

        # خصم النقاط (غير الأدمن)
        if bal != -1:
            db.add_balance(user_id, -price)

        type_ar = PLATFORM_TO_AR.get(platform, platform)

        msg = (
            "تم الشراء بنجاح ✅\n\n"
            f"النوع: {type_ar}\n"
            f"الإيميل: {acc.get('email') or '-'}\n"
            f"اليوزر: {acc.get('username')}\n"
            f"الباسورد: {acc.get('password')}\n"
            f"السعر: {price} نقطة\n"
        )
        bot.send_message(m.chat.id, msg)