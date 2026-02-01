# handlers_email.py
# دمج "طلب ايميل -> ايميل مؤقت" (إيميل واحد لكل مستخدم)
# سياسة الخصم: مرة واحدة فقط لكل إيميل عند ظهور أول (كود أو رابط تفعيل)
# عربي بالكامل

from telebot.types import Message, ReplyKeyboardMarkup, KeyboardButton
import db
from config import ADMIN_USER_ID, TEMP_EMAIL_PRICE, TEMP_EMAIL_PAID, TEMP_EMAIL_SHOW_LIMIT
from tempmail import email_engine


BTN_BACK = "رجوع"
BTN_TEMP = "ايميل مؤقت"
BTN_REFRESH = "تحديث الرسائل"
BTN_NEW = "إيميل جديد"
BTN_LAST = "آخر إيميل"

# سياق بسيط لمنع تداخل زر "رجوع" مع أقسام أخرى
# user_id -> True/False
_email_ctx = {}


def _kb(rows):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for row in rows:
        if isinstance(row, (list, tuple)):
            kb.row(*[KeyboardButton(str(x)) for x in row])
        else:
            kb.add(KeyboardButton(str(row)))
    return kb


def _is_admin_unlimited(user_id: int) -> bool:
    return db.get_balance(user_id) == -1.0


def _go_main(bot, m: Message, build_main_keyboard):
    """يرجع للقائمة الرئيسية مباشرة (مع كيبورد صحيح للأدمن/مستخدم)."""
    _email_ctx.pop(m.from_user.id, None)
    if build_main_keyboard is None:
        bot.send_message(m.chat.id, "رجعت للقائمة الرئيسية. استخدم /start لعرض القائمة.")
        return
    is_admin = (m.from_user.id == ADMIN_USER_ID)
    bot.send_message(
        m.chat.id,
        "القائمة الرئيسية:",
        reply_markup=build_main_keyboard(is_admin)
    )


def _need_charge(active: dict, user_id: int) -> bool:
    """هل يلزم الخصم الآن؟ (مدفوع + ليس أدمن unlimited + لم يُخصم بعد)"""
    return (
        TEMP_EMAIL_PAID
        and (not _is_admin_unlimited(user_id))
        and int((active or {}).get("charged", 0)) == 0
    )


def _ensure_charge_or_block(bot, chat_id: int, user_id: int, active: dict) -> bool:
    """
    يطبق الخصم مرة واحدة، أو يمنع العرض إذا الرصيد غير كافٍ.
    يرجع True إذا مسموح بالعرض، False إذا ممنوع.
    """
    if not _need_charge(active, user_id):
        return True

    bal = db.get_balance(user_id)
    if bal < float(TEMP_EMAIL_PRICE):
        bot.send_message(
            chat_id,
            f"وصلت رسالة تفعيل، لكن رصيدك غير كافٍ لعرضها.\n"
            f"السعر: {TEMP_EMAIL_PRICE} نقطة\nرصيدك: {bal}\n\n"
            f"اشحن رصيدك ثم اضغط (تحديث الرسائل)."
        )
        return False

    db.add_balance(user_id, -float(TEMP_EMAIL_PRICE))
    db.mark_temp_email_charged(user_id)
    return True


def register_email_handlers(bot, build_main_keyboard=None):

    # ====== Menu: طلب ايميل ======
    @bot.message_handler(func=lambda m: (m.text or "").strip() == "طلب ايميل")
    def email_menu(m: Message):
        _email_ctx[m.from_user.id] = True
        bot.send_message(
            m.chat.id,
            "اختر نوع الإيميل:",
            reply_markup=_kb([[BTN_TEMP], [BTN_BACK]])
        )

    # ====== رجوع (داخل قسم الإيميل فقط) ======
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_BACK and _email_ctx.get(m.from_user.id) is True)
    def back(m: Message):
        _go_main(bot, m, build_main_keyboard)

    # ====== ايميل مؤقت (إيميل واحد) ======
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_TEMP)
    def temp_email_entry(m: Message):
        _email_ctx[m.from_user.id] = True

        user_id = m.from_user.id
        db.register_user(user_id, is_admin=(user_id == ADMIN_USER_ID))

        active = db.get_active_temp_email(user_id)
        if active:
            kb = _kb([[BTN_REFRESH, BTN_LAST], [BTN_NEW], [BTN_BACK]])
            bot.send_message(
                m.chat.id,
                f"لديك إيميل نشط:\n{active['email']}\n\nاختر خياراً:",
                reply_markup=kb
            )
            return

        _create_new_email(m)

    # ====== آخر ايميل ======
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_LAST)
    def last_email(m: Message):
        _email_ctx[m.from_user.id] = True

        user_id = m.from_user.id
        active = db.get_active_temp_email(user_id)
        if not active:
            bot.send_message(m.chat.id, "لا يوجد إيميل نشط. اضغط: ايميل مؤقت")
            return

        kb = _kb([[BTN_REFRESH, BTN_LAST], [BTN_NEW], [BTN_BACK]])
        bot.send_message(m.chat.id, f"آخر إيميل لديك:\n{active['email']}", reply_markup=kb)

    # ====== ايميل جديد (استبدال) ======
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_NEW)
    def new_email(m: Message):
        _email_ctx[m.from_user.id] = True
        _create_new_email(m)

    def _create_new_email(m: Message):
        user_id = m.from_user.id

        bot.send_message(m.chat.id, "جاري إنشاء إيميل جديد...")
        try:
            info = email_engine.create_email_from_utils(m)
        except Exception as e:
            bot.send_message(m.chat.id, f"فشل إنشاء الإيميل.\nسبب الخطأ: {e}")
            return

        # حفظه كإيميل نشط (charged=0 تلقائياً)
        db.set_active_temp_email(user_id, info["email"], info["token"])

        kb = _kb([[BTN_REFRESH, BTN_LAST], [BTN_NEW], [BTN_BACK]])
        paid_note = "الخدمة مدفوعة عند ظهور أول (كود أو رابط تفعيل)." if TEMP_EMAIL_PAID else "الخدمة مجانية حالياً."
        bot.send_message(
            m.chat.id,
            f"تم إنشاء الإيميل ✅\n\n{info['email']}\n\n{paid_note}",
            reply_markup=kb
        )

    # ====== تحديث الرسائل ======
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_REFRESH)
    def refresh_inbox(m: Message):
        _email_ctx[m.from_user.id] = True

        user_id = m.from_user.id
        active = db.get_active_temp_email(user_id)
        if not active:
            bot.send_message(m.chat.id, "لا يوجد إيميل نشط للتحديث. اضغط: ايميل مؤقت")
            return

        token = active["token"]

        try:
            messages = email_engine.fetch_latest_messages(token, limit=int(TEMP_EMAIL_SHOW_LIMIT))
        except Exception as e:
            bot.send_message(m.chat.id, f"تعذر جلب الرسائل الآن.\nسبب الخطأ: {e}")
            return

        if not messages:
            bot.send_message(m.chat.id, "لا توجد رسائل حتى الآن.")
            return

        # 1) محاولة استخراج OTP أولاً
        found_code = ""
        found_msg = ""
        for msg in messages:
            code = email_engine.extract_otp_code(msg)
            if code:
                found_code = code
                found_msg = msg
                break

        if found_code:
            # سياسة الخصم: مرة واحدة لكل ايميل عند أول فائدة
            if not _ensure_charge_or_block(bot, m.chat.id, user_id, active):
                return

            note = ""
            if TEMP_EMAIL_PAID and (not _is_admin_unlimited(user_id)):
                if int(active.get("charged", 0)) == 0:
                    note = f"\n\nتم خصم {TEMP_EMAIL_PRICE} نقطة (مرة واحدة لهذا الإيميل)."
                else:
                    note = "\n\n(لا يوجد خصم إضافي لهذا الإيميل)."

            bot.send_message(
                m.chat.id,
                f"تم العثور على كود ✅: {found_code}{note}\n\nآخر رسالة:\n{found_msg}"
            )
            return

        # 2) إذا لا يوجد OTP: حاول استخراج رابط تفعيل
        found_link = ""
        found_link_msg = ""
        for msg in messages:
            link = ""
            # إذا أضفت extract_first_link في email_engine.py
            if hasattr(email_engine, "extract_first_link"):
                link = email_engine.extract_first_link(msg)
            if link:
                found_link = link
                found_link_msg = msg
                break

        if found_link:
            if not _ensure_charge_or_block(bot, m.chat.id, user_id, active):
                return

            note = ""
            if TEMP_EMAIL_PAID and (not _is_admin_unlimited(user_id)):
                if int(active.get("charged", 0)) == 0:
                    note = f"\n\nتم خصم {TEMP_EMAIL_PRICE} نقطة (مرة واحدة لهذا الإيميل)."
                else:
                    note = "\n\n(لا يوجد خصم إضافي لهذا الإيميل)."

            bot.send_message(
                m.chat.id,
                f"تم العثور على رابط تفعيل ✅:{note}\n{found_link}\n\nآخر رسالة:\n{found_link_msg}"
            )
            return

        # 3) لا كود ولا رابط: اعرض الرسائل كما هي
        out = "\n\n".join([f"{i+1})\n{t}" for i, t in enumerate(messages)])
        bot.send_message(m.chat.id, "📩 آخر الرسائل:\n\n" + out)