# earn/handlers_earn.py
# ربح نقاط: (مواقع + سحب USDT) - سيتم تطويره لاحقاً خطوة خطوة

from telebot import types
from telebot.types import Message

BTN_EARN = "ربح نقاط"
BTN_BACK = "رجوع"

BTN_SITES = "مواقع"
BTN_WITHDRAW = "سحب"

_ctx = {}  # user_id -> True/False


def _kb(rows):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for row in rows:
        if isinstance(row, (list, tuple)):
            kb.row(*[types.KeyboardButton(str(x)) for x in row])
        else:
            kb.add(types.KeyboardButton(str(row)))
    return kb


def _earn_menu_kb():
    return _kb([
        [BTN_SITES, BTN_WITHDRAW],
        [BTN_BACK],
    ])


def register_earn_handlers(bot, build_main_keyboard=None, is_admin_fn=None):
    # دخول قائمة ربح نقاط
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_EARN)
    def earn_entry(m: Message):
        _ctx[m.from_user.id] = True
        bot.send_message(m.chat.id, "ربح نقاط: اختر خياراً:", reply_markup=_earn_menu_kb())

    # رجوع للقائمة الرئيسية (داخل ربح نقاط فقط)
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_BACK and _ctx.get(m.from_user.id) is True)
    def earn_back(m: Message):
        _ctx.pop(m.from_user.id, None)
        if build_main_keyboard is None:
            bot.send_message(m.chat.id, "رجعت للقائمة الرئيسية. استخدم /start.")
            return
        is_admin = bool(is_admin_fn(m.from_user.id)) if is_admin_fn else False
        bot.send_message(m.chat.id, "القائمة الرئيسية:", reply_markup=build_main_keyboard(is_admin))

    # مواقع (مؤقتاً)
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_SITES)
    def earn_sites(m: Message):
        _ctx[m.from_user.id] = True
        bot.send_message(m.chat.id, "قريباً: عرض الأقسام والمواقع.", reply_markup=_earn_menu_kb())

    # سحب (مؤقتاً)
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_WITHDRAW)
    def earn_withdraw(m: Message):
        _ctx[m.from_user.id] = True
        bot.send_message(m.chat.id, "قريباً: سحب عبر USDT + TXID.", reply_markup=_earn_menu_kb())