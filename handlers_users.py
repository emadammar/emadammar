# handlers_users.py
# إدارة المشتركين للأدمن:
# - آخر 10 مشتركين
# - بحث
# - إرسال رصيد مباشرة بدون نسخ ID

import time
from telebot import types
from telebot.types import Message

import db
from config import ADMIN_USER_ID


BTN_USERS = "اسماء المشتركين"
BTN_LAST10 = "آخر 10 مشتركين"
BTN_SEARCH = "بحث"
BTN_BACK = "رجوع"

CB_USER = "usr:"          # usr:<id>
CB_SEND = "sendbal:"      # sendbal:<id>


def _name_of(u: dict) -> str:
    fn = (u.get("first_name") or "").strip()
    ln = (u.get("last_name") or "").strip()
    un = (u.get("username") or "").strip()
    name = (fn + " " + ln).strip()
    if name:
        return name
    if un:
        return f"@{un}"
    return str(u.get("user_id", ""))


def register_users_handlers(bot, build_main_keyboard=None):

    def _go_main(m: Message):
        if build_main_keyboard is None:
            bot.send_message(m.chat.id, "رجعت للقائمة الرئيسية. استخدم /start.")
            return
        is_admin = (m.from_user.id == ADMIN_USER_ID)
        bot.send_message(m.chat.id, "القائمة الرئيسية:", reply_markup=build_main_keyboard(is_admin))

    def _admin_only(m: Message) -> bool:
        return m.from_user.id == ADMIN_USER_ID

    def _menu(chat_id: int):
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        kb.add(types.KeyboardButton(BTN_LAST10), types.KeyboardButton(BTN_SEARCH))
        kb.add(types.KeyboardButton(BTN_BACK))
        bot.send_message(chat_id, "قسم المشتركين:", reply_markup=kb)

    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_USERS and _admin_only(m))
    def users_entry(m: Message):
        _menu(m.chat.id)

    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_BACK and _admin_only(m))
    def users_back(m: Message):
        _go_main(m)

    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_LAST10 and _admin_only(m))
    def last10(m: Message):
        users = db.list_last_users(limit=10)
        if not users:
            bot.send_message(m.chat.id, "لا يوجد مستخدمين محفوظين بعد. (يظهرون بعد ما يستخدموا /start)")
            return

        ikb = types.InlineKeyboardMarkup()
        for u in users:
            uid = int(u["user_id"])
            title = f"{_name_of(u)} — {uid}"
            ikb.add(types.InlineKeyboardButton(title, callback_data=f"{CB_USER}{uid}"))
        bot.send_message(m.chat.id, "آخر 10 مشتركين:", reply_markup=ikb)

    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_SEARCH and _admin_only(m))
    def ask_search(m: Message):
        msg = bot.send_message(m.chat.id, "اكتب كلمة البحث (ID أو username أو الاسم):")
        bot.register_next_step_handler(msg, _do_search)

    def _do_search(m: Message):
        if m.from_user.id != ADMIN_USER_ID:
            return
        q = (m.text or "").strip()
        users = db.search_users(q, limit=20)
        if not users:
            bot.send_message(m.chat.id, "لا توجد نتائج.")
            return

        ikb = types.InlineKeyboardMarkup()
        for u in users:
            uid = int(u["user_id"])
            title = f"{_name_of(u)} — {uid}"
            ikb.add(types.InlineKeyboardButton(title, callback_data=f"{CB_USER}{uid}"))
        bot.send_message(m.chat.id, "نتائج البحث:", reply_markup=ikb)

    @bot.callback_query_handler(func=lambda c: (c.data or "").startswith(CB_USER))
    def cb_user(call):
        try:
            uid = int(call.data.split(":", 1)[1])
        except Exception:
            bot.answer_callback_query(call.id, "خطأ في المستخدم")
            return

        if call.from_user.id != ADMIN_USER_ID:
            bot.answer_callback_query(call.id, "غير مصرح")
            return

        # عرض بطاقة المستخدم + زر إرسال رصيد
        ikb = types.InlineKeyboardMarkup()
        ikb.add(types.InlineKeyboardButton("إرسال رصيد لهذا المستخدم", callback_data=f"{CB_SEND}{uid}"))

        bot.send_message(
            call.message.chat.id,
            f"المستخدم المختار:\nID: {uid}\n\nاضغط لإرسال رصيد مباشرة:",
            reply_markup=ikb
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: (c.data or "").startswith(CB_SEND))
    def cb_send(call):
        if call.from_user.id != ADMIN_USER_ID:
            bot.answer_callback_query(call.id, "غير مصرح")
            return

        try:
            uid = int(call.data.split(":", 1)[1])
        except Exception:
            bot.answer_callback_query(call.id, "خطأ")
            return

        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, f"اكتب مبلغ الرصيد لإرساله للمستخدم {uid}:")
        bot.register_next_step_handler(msg, _send_amount_step, uid)

    def _send_amount_step(m: Message, recipient_id: int):
        if m.from_user.id != ADMIN_USER_ID:
            return

        try:
            amount = float((m.text or "").strip())
        except Exception:
            bot.send_message(m.chat.id, "مبلغ غير صحيح. اكتب رقم فقط.")
            return

        ok, reason = db.transfer_balance(ADMIN_USER_ID, int(recipient_id), float(amount))
        if not ok:
            bot.send_message(m.chat.id, f"فشل الإرسال: {reason}")
            return

        bot.send_message(m.chat.id, f"تم إرسال {amount} نقطة للمستخدم {recipient_id} بنجاح.")