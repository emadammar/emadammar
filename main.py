# main.py
# تشغيل البوت وربط القوائم والـ handlers
# متوافق 100% مع Pydroid3 + Termux + Railway Public URL

import telebot
from telebot import types

from flask import Flask
import threading
import os

import db
from config import (
    BOT_TOKEN,
    ADMIN_USER_ID,
    POLLING_TIMEOUT,
    LONG_POLLING_TIMEOUT,
    REFERRAL_REWARD,
)

from handlers_users import register_users_handlers
from handlers_waseena import register_waseena_handlers

from handlers_balance import register_balance_handlers
from handlers_accounts import register_accounts_handlers
from handlers_numbers import register_numbers_handlers
from handlers_email import register_email_handlers

# ربح المال (مواقع فقط)
from earn.handlers_earn_money import register_earn_money_handlers

# ================== Keyboards ==================

def build_main_keyboard(is_admin: bool):
    kb = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)

    kb.add(types.KeyboardButton("رصيدي"))
    kb.add(types.KeyboardButton("طلب رقم"), types.KeyboardButton("طلب ايميل"))
    kb.add(types.KeyboardButton("حسابات تواصل"))
    kb.add(types.KeyboardButton("وصينا"))

    kb.add(types.KeyboardButton("💰 ربح المال"))
    kb.add(types.KeyboardButton("🔗 رابط الإحالة"))

    # ✅ زر معلومات التواصل
    kb.add(types.KeyboardButton("📞 معلومات التواصل"))

    if is_admin:
        kb.add(types.KeyboardButton("إرسال رصيد"), types.KeyboardButton("إضافة حساب"))
        kb.add(types.KeyboardButton("اسماء المشتركين"))

    return kb


def build_accounts_keyboard():
    kb = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.add(types.KeyboardButton("فيسبوك"), types.KeyboardButton("إنستغرام"))
    kb.add(types.KeyboardButton("تويتر"), types.KeyboardButton("رجوع"))
    return kb

# ================== Flask Server ==================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running 🚀"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# شغّل السيرفر في Thread عشان ما يوقف البوت
threading.Thread(target=run_flask).start()

# ================== Main ==================

def main():
    # init db
    db.init_db()
    db.register_user(ADMIN_USER_ID, is_admin=True)

    bot = telebot.TeleBot(BOT_TOKEN)

    # ---------- Helper ----------
    def go_home(chat_id: int, user_id: int, text: str = "اختر من القائمة:"):
        is_admin = (user_id == ADMIN_USER_ID)
        bot.send_message(chat_id, text, reply_markup=build_main_keyboard(is_admin))

    # ---------- Register handlers ----------
    register_numbers_handlers(bot)
    register_balance_handlers(bot)
    register_accounts_handlers(bot)
    register_email_handlers(bot, build_main_keyboard)
    register_users_handlers(bot, build_main_keyboard)
    register_waseena_handlers(bot, build_main_keyboard)
    register_earn_money_handlers(bot, build_main_keyboard)

    # ---------- Global Cancel ----------
    @bot.message_handler(func=lambda m: (m.text or "").strip() in ("إلغاء", "الغاء"))
    def global_cancel(m):
        try:
            bot.clear_step_handler_by_chat_id(m.chat.id)
        except Exception:
            pass

        try:
            import state
            if state.has_active_order(m.from_user.id):
                state.clear_order(m.from_user.id)
        except Exception:
            pass

        try:
            if hasattr(db, "clear_active_temp_email"):
                db.clear_active_temp_email(m.from_user.id)
        except Exception:
            pass

        go_home(m.chat.id, m.from_user.id, "تم الإلغاء. اختر من القائمة:")

    # ---------- Start + Referral ----------
    @bot.message_handler(commands=["start"])
    def start_handler(message):
        user_id = message.from_user.id
        is_admin = (user_id == ADMIN_USER_ID)

        args = message.text.split(maxsplit=1)
        referrer_id = None

        if len(args) > 1 and args[1].startswith("ref_"):
            try:
                referrer_id = int(args[1][4:])
            except Exception:
                pass

        db.register_user(user_id, is_admin=is_admin)

        if referrer_id and referrer_id != user_id:
            if not db.has_referrer(user_id):
                db.set_referrer(user_id, referrer_id)
                db.add_points(referrer_id, REFERRAL_REWARD)

        u = message.from_user
        db.upsert_user_profile(
            user_id=u.id,
            username=getattr(u, "username", "") or "",
            first_name=getattr(u, "first_name", "") or "",
            last_name=getattr(u, "last_name", "") or "",
        )

        bot.send_message(
            message.chat.id,
            "أهلاً وسهلاً 👋\nاختر من القائمة:",
            reply_markup=build_main_keyboard(is_admin)
        )

    # ---------- Balance ----------
    @bot.message_handler(func=lambda m: (m.text or "").strip() == "رصيدي")
    def show_balance(m):
        bal = db.get_balance(m.from_user.id)
        if bal == -1:
            bot.send_message(m.chat.id, "رصيد الأدمن: غير محدود (-1).")
        else:
            bot.send_message(m.chat.id, f"رصيدك الحالي: {bal}")

    # ---------- Accounts ----------
    @bot.message_handler(func=lambda m: (m.text or "").strip() == "حسابات تواصل")
    def accounts_menu(m):
        bot.send_message(
            m.chat.id,
            "اختر نوع الحساب:",
            reply_markup=build_accounts_keyboard()
        )

    # ---------- Referral Link ----------
    @bot.message_handler(func=lambda m: (m.text or "").strip() == "🔗 رابط الإحالة")
    def referral_link(m):
        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start=ref_{m.from_user.id}"

        bot.send_message(
            m.chat.id,
            f"🔗 رابط الإحالة الخاص بك:\n\n"
            f"{link}\n\n"
            f"🎁 ستحصل على {REFERRAL_REWARD} نقاط عن كل إحالة ناجحة"
        )

    # ---------- Contact Info ----------
    @bot.message_handler(func=lambda m: (m.text or "").strip() == "📞 معلومات التواصل")
    def contact_info(m):
        bot.send_message(
            m.chat.id,
            "📞 معلومات التواصل\n\n"
            "🧑‍💻 الدعم الفني:\n"
            "👉 @emad09344\n\n"
            "📢 قناة التحديثات:\n"
            "👉 eee \n\n"
            "⏰ وقت الدعم:\n"
            "من 10 صباحاً إلى 10 مساءً"
        )

    # ---------- Run ----------
    bot.polling(
        timeout=POLLING_TIMEOUT,
        long_polling_timeout=LONG_POLLING_TIMEOUT
    )


if __name__ == "__main__":
    main()