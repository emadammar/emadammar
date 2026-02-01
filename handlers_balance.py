# handlers_balance.py
# أوامر الرصيد: Check Balance + Send Balance (للأدمن فقط)
# متوافق 100% مع Pydroid3 + Termux

from telebot.types import Message

from config import ADMIN_USER_ID
import db


def register_balance_handlers(bot):
    # يدعم العربي + الإنجليزي
    @bot.message_handler(func=lambda m: (m.text or "").strip() in ("Check Balance", "رصيدي", "عرض الرصيد"))
    def _check_balance(m: Message):
        user_id = m.from_user.id
        db.register_user(user_id, is_admin=(user_id == ADMIN_USER_ID))
        bal = db.get_balance(user_id)

        # عرض عربي للمستخدم
        if bal == -1:
            bot.reply_to(m, "رصيد الأدمن: غير محدود (-1).")
        else:
            bot.reply_to(m, f"رصيدك الحالي: {bal}")

    # يدعم العربي + الإنجليزي (زر الأدمن الجديد: إرسال رصيد)
    @bot.message_handler(func=lambda m: (m.text or "").strip() in ("Send Balance", "إرسال رصيد"))
    def _send_balance(m: Message):
        user_id = m.from_user.id
        if user_id != ADMIN_USER_ID:
            bot.reply_to(m, "لا تملك صلاحية إرسال الرصيد.")
            return

        msg = bot.reply_to(m, "أدخل رقم المستخدم (User ID) الذي تريد إرسال الرصيد له:")
        bot.register_next_step_handler(msg, _step_recipient)

    def _step_recipient(m: Message):
        # دعم زر الإلغاء داخل الخطوات
        if (m.text or "").strip() in ("إلغاء", "الغاء"):
            try:
                bot.clear_step_handler_by_chat_id(m.chat.id)
            except Exception:
                pass
            bot.reply_to(m, "تم الإلغاء.")
            return

        try:
            recipient_id = int(str(m.text).strip())
        except Exception:
            msg = bot.reply_to(m, "رقم المستخدم غير صحيح. أدخل أرقام فقط:")
            bot.register_next_step_handler(msg, _step_recipient)
            return

        msg = bot.reply_to(m, "أدخل المبلغ المراد إرساله:")
        bot.register_next_step_handler(msg, _step_amount, recipient_id)

    def _step_amount(m: Message, recipient_id: int):
        # دعم زر الإلغاء داخل الخطوات
        if (m.text or "").strip() in ("إلغاء", "الغاء"):
            try:
                bot.clear_step_handler_by_chat_id(m.chat.id)
            except Exception:
                pass
            bot.reply_to(m, "تم الإلغاء.")
            return

        try:
            amount = float(str(m.text).strip())
            if amount <= 0:
                raise ValueError()
        except Exception:
            msg = bot.reply_to(m, "المبلغ غير صحيح. أدخل رقم أكبر من 0:")
            bot.register_next_step_handler(msg, _step_amount, recipient_id)
            return

        # سجل المستخدمين إذا غير موجودين
        db.register_user(ADMIN_USER_ID, is_admin=True)
        db.register_user(recipient_id, is_admin=False)

        ok, reason = db.transfer_balance(ADMIN_USER_ID, recipient_id, amount)
        if not ok:
            bot.reply_to(m, f"فشل الإرسال: {reason}")
            return

        bot.reply_to(m, f"تم إرسال {amount} نقطة إلى المستخدم {recipient_id} بنجاح.")