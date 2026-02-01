# handlers_numbers.py
# تحديث: دول ثابتة بأزرار عربية مع صفحات (5 دول لكل صفحة)
# + فئات وخدمات شائعة بالعربي
# + زر رجوع للدول + زر رجوع للفئات + قائمة إنقاذ عند عدم توفر الخدمة
# + حماية من بعض الأخطاء التي تسبب توقف التدفق

from telebot.types import Message, ReplyKeyboardMarkup, KeyboardButton

import db
import state
import vak_api
import catalog_cache
import service_catalog_ar

from config import (
    VAK_API_KEY,
    ORDER_TIMEOUT_SECONDS,
    ADMIN_USER_ID,
)

# =========================
# Countries (fixed list)
# =========================
PAGE_SIZE = 5
COUNTRIES = [
    ("كندا", "36"),
    ("فرنسا", "78"),
    ("ألمانيا", "43"),
    ("اليونان", "129"),
    ("إندونيسيا", "6"),
    ("العراق", "47"),
    ("إسرائيل", "13"),
    ("الأردن", "116"),
    ("روسيا", "0"),
    ("السعودية", "53"),
    ("إسبانيا", "56"),
    ("سوريا", "110"),
    ("المملكة المتحدة", "16"),
    ("الولايات المتحدة", "187"),
    ("فيتنام", "10"),
]

BTN_NEXT = "التالي"
BTN_PREV = "السابق"
BTN_CANCEL = "إلغاء"
BTN_BACK_CATS = "رجوع للفئات"
BTN_SEARCH_SERVICE = "بحث عن خدمة"
BTN_BACK_COUNTRIES = "رجوع للدول"

# صفحة الدول لكل مستخدم (RAM)
_user_country_page = {}


def _kb(*rows):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for r in rows:
        if isinstance(r, (list, tuple)):
            for b in r:
                kb.add(KeyboardButton(str(b)))
        else:
            kb.add(KeyboardButton(str(r)))
    return kb


def register_numbers_handlers(bot):

    # =========================
    # Safety wrapper (prevents "stuck" due to exceptions)
    # =========================
    def _safe_call(m: Message, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            try:
                bot.send_message(
                    m.chat.id,
                    "حدث خطأ مؤقت. استخدم (رجوع للدول) لإعادة المحاولة."
                )
            except Exception:
                pass
            return None

    # ===== Menu =====
    @bot.message_handler(func=lambda m: m.text == "طلب رقم")
    def numbers_menu(m: Message):
        kb = _kb(["طلب رقم جديد"], ["رجوع"])
        bot.send_message(m.chat.id, "اختر:", reply_markup=kb)

    @bot.message_handler(func=lambda m: m.text == "رجوع")
    def back(m: Message):
        bot.send_message(m.chat.id, "العودة للقائمة الرئيسية. اكتب /start")

    # ===== Start flow =====
    @bot.message_handler(func=lambda m: m.text == "طلب رقم جديد")
    def start_flow(m: Message):
        user_id = m.from_user.id
        _ensure_user(user_id)

        if _block_if_busy(bot, m, user_id):
            return

        _user_country_page[user_id] = 0
        _show_countries_page(m.chat.id, user_id)

    # =========================
    # Country paging (fixed)
    # =========================
    def _show_countries_page(chat_id: int, user_id: int):
        page = _user_country_page.get(user_id, 0)
        total = len(COUNTRIES)
        max_page = (total - 1) // PAGE_SIZE

        if page < 0:
            page = 0
        if page > max_page:
            page = max_page
        _user_country_page[user_id] = page

        start = page * PAGE_SIZE
        end = min(start + PAGE_SIZE, total)
        page_items = COUNTRIES[start:end]

        rows = []
        for name, _cid in page_items:
            rows.append([name])

        nav = []
        if page > 0:
            nav.append(BTN_PREV)
        if page < max_page:
            nav.append(BTN_NEXT)
        if nav:
            rows.append(nav)

        rows.append([BTN_CANCEL])

        bot.send_message(
            chat_id,
            f"اختر الدولة (صفحة {page + 1}/{max_page + 1}):",
            reply_markup=_kb(*rows),
        )
        bot.register_next_step_handler_by_chat_id(chat_id, choose_country_fixed)

    def _country_id_from_name(name: str):
        for n, cid in COUNTRIES:
            if n == name:
                return cid
        return None

    def choose_country_fixed(m: Message):
        user_id = m.from_user.id
        if _block_if_busy(bot, m, user_id):
            return

        text = (m.text or "").strip()

        if text == BTN_CANCEL:
            bot.send_message(m.chat.id, "تم الإلغاء.")
            return

        if text == BTN_NEXT:
            _user_country_page[user_id] = _user_country_page.get(user_id, 0) + 1
            _show_countries_page(m.chat.id, user_id)
            return

        if text == BTN_PREV:
            _user_country_page[user_id] = _user_country_page.get(user_id, 0) - 1
            _show_countries_page(m.chat.id, user_id)
            return

        country_id = _country_id_from_name(text)
        if not country_id:
            bot.send_message(m.chat.id, "اختيار غير صالح. اختر دولة من الأزرار.")
            _show_countries_page(m.chat.id, user_id)
            return

        _ask_category(m.chat.id, country_id, country_name=text)

    # =========================
    # Rescue menu (when service not available or errors)
    # =========================
    def _rescue_menu(chat_id: int, user_id: int, country_id: str, country_name: str, reason: str):
        kb = _kb(
            [BTN_BACK_CATS],
            [BTN_SEARCH_SERVICE],
            [BTN_BACK_COUNTRIES],
            [BTN_CANCEL],
        )
        bot.send_message(chat_id, reason, reply_markup=kb)
        bot.register_next_step_handler_by_chat_id(chat_id, rescue_menu_handler, country_id, country_name)

    def rescue_menu_handler(m: Message, country_id: str, country_name: str):
        user_id = m.from_user.id
        text = (m.text or "").strip()

        if text == BTN_CANCEL:
            bot.send_message(m.chat.id, "تم الإلغاء.")
            return

        if text == BTN_BACK_CATS:
            _ask_category(m.chat.id, country_id, country_name)
            return

        if text == BTN_SEARCH_SERVICE:
            msg = bot.send_message(
                m.chat.id,
                "اكتب رمز الخدمة أو جزء من الاسم (مثل: wa, tg, fb):",
                reply_markup=_kb([BTN_BACK_CATS], [BTN_BACK_COUNTRIES], [BTN_CANCEL]),
            )
            bot.register_next_step_handler(msg, provider_search_service, country_id, country_name)
            return

        if text == BTN_BACK_COUNTRIES:
            _user_country_page[user_id] = 0
            _show_countries_page(m.chat.id, user_id)
            return

        _rescue_menu(m.chat.id, user_id, country_id, country_name, "اختيار غير صالح. اختر زر من القائمة.")

    # =========================
    # Category selection
    # =========================
    def _ask_category(chat_id: int, country_id: str, country_name: str):
        cats = service_catalog_ar.get_categories()
        rows = [[title] for _, title in cats]
        rows.append([BTN_SEARCH_SERVICE])
        rows.append([BTN_BACK_COUNTRIES])
        rows.append([BTN_CANCEL])

        bot.send_message(
            chat_id,
            f"الدولة المختارة: {country_name}\nاختر الفئة:",
            reply_markup=_kb(*rows),
        )
        bot.register_next_step_handler_by_chat_id(chat_id, choose_category, country_id, country_name)

    def choose_category(m: Message, country_id: str, country_name: str):
        user_id = m.from_user.id
        if _block_if_busy(bot, m, user_id):
            return

        text = (m.text or "").strip()

        if text == BTN_CANCEL:
            bot.send_message(m.chat.id, "تم الإلغاء.")
            return

        if text == BTN_BACK_COUNTRIES:
            _user_country_page[user_id] = 0
            _show_countries_page(m.chat.id, user_id)
            return

        if text == BTN_SEARCH_SERVICE:
            msg = bot.send_message(
                m.chat.id,
                "اكتب رمز الخدمة أو جزء من الاسم (مثل: wa, tg, fb):",
                reply_markup=_kb([BTN_BACK_COUNTRIES], [BTN_CANCEL]),
            )
            bot.register_next_step_handler(msg, provider_search_service, country_id, country_name)
            return

        cat_key = None
        for key, title in service_catalog_ar.get_categories():
            if text == title:
                cat_key = key
                break

        if not cat_key:
            bot.send_message(m.chat.id, "اختيار فئة غير صالح.")
            _ask_category(m.chat.id, country_id, country_name)
            return

        _show_common_services(m.chat.id, country_id, country_name, cat_key)

    # =========================
    # Common services in category
    # =========================
    def _show_common_services(chat_id: int, country_id: str, country_name: str, cat_key: str):
        items = service_catalog_ar.get_common_services(cat_key)
        if not items:
            bot.send_message(chat_id, "لا توجد خدمات شائعة في هذه الفئة.")
            _ask_category(chat_id, country_id, country_name)
            return

        rows = [[f"{it.ar} — ({it.code})"] for it in items]
        rows.append([BTN_SEARCH_SERVICE])
        rows.append([BTN_BACK_CATS])
        rows.append([BTN_BACK_COUNTRIES])
        rows.append([BTN_CANCEL])

        cat_title = next((t for k, t in service_catalog_ar.get_categories() if k == cat_key), "الفئة")
        bot.send_message(
            chat_id,
            f"{cat_title}\nاختر الخدمة:",
            reply_markup=_kb(*rows),
        )
        bot.register_next_step_handler_by_chat_id(chat_id, choose_common_service, country_id, country_name)

    def _extract_code_from_label(text: str) -> str:
        t = (text or "").strip()
        if "(" in t and ")" in t:
            inside = t[t.rfind("(") + 1 : t.rfind(")")]
            return inside.strip()
        return t

    def choose_common_service(m: Message, country_id: str, country_name: str):
        user_id = m.from_user.id
        if _block_if_busy(bot, m, user_id):
            return

        text = (m.text or "").strip()

        if text == BTN_CANCEL:
            bot.send_message(m.chat.id, "تم الإلغاء.")
            return

        if text == BTN_BACK_CATS:
            _ask_category(m.chat.id, country_id, country_name)
            return

        if text == BTN_BACK_COUNTRIES:
            _user_country_page[user_id] = 0
            _show_countries_page(m.chat.id, user_id)
            return

        if text == BTN_SEARCH_SERVICE:
            msg = bot.send_message(
                m.chat.id,
                "اكتب رمز الخدمة أو جزء من الاسم (مثل: wa, tg, fb):",
                reply_markup=_kb([BTN_BACK_CATS], [BTN_BACK_COUNTRIES], [BTN_CANCEL]),
            )
            bot.register_next_step_handler(msg, provider_search_service, country_id, country_name)
            return

        service_code = _extract_code_from_label(text)
        if not service_code:
            _rescue_menu(m.chat.id, user_id, country_id, country_name, "خدمة غير صالحة.")
            return

        entry = _safe_call(m, catalog_cache.get_service_entry, country_id, service_code)
        if not entry:
            _rescue_menu(
                m.chat.id,
                user_id,
                country_id,
                country_name,
                "هذه الخدمة غير متاحة في هذه الدولة حالياً.\n"
                "اختر (رجوع للفئات) أو (بحث عن خدمة) أو (رجوع للدول)."
            )
            return

        _confirm_service(m, country_id, country_name, service_code, float(entry["sell"]))

    # =========================
    # Provider search (all services)
    # =========================
    def provider_search_service(m: Message, country_id: str, country_name: str):
        user_id = m.from_user.id
        if _block_if_busy(bot, m, user_id):
            return

        text = (m.text or "").strip()
        if text == BTN_CANCEL:
            bot.send_message(m.chat.id, "تم الإلغاء.")
            return

        if text == BTN_BACK_COUNTRIES:
            _user_country_page[user_id] = 0
            _show_countries_page(m.chat.id, user_id)
            return

        results = _safe_call(m, catalog_cache.search_services, country_id, text, limit=12) or []
        if not results:
            _rescue_menu(
                m.chat.id,
                user_id,
                country_id,
                country_name,
                "لا توجد خدمات مطابقة في هذه الدولة.\n"
                "اختر (رجوع للفئات) أو (رجوع للدول)."
            )
            return

        rows = []
        for e in results:
            code = e["service"]
            label = service_catalog_ar.format_service_label(code)
            rows.append([f"{label} | السعر: {e['sell']}"])

        rows.append([BTN_BACK_CATS])
        rows.append([BTN_BACK_COUNTRIES])
        rows.append([BTN_CANCEL])

        bot.send_message(m.chat.id, "نتائج البحث:", reply_markup=_kb(*rows))
        bot.register_next_step_handler(m, choose_provider_search_result, country_id, country_name)

    def choose_provider_search_result(m: Message, country_id: str, country_name: str):
        user_id = m.from_user.id
        if _block_if_busy(bot, m, user_id):
            return

        text = (m.text or "").strip()

        if text == BTN_CANCEL:
            bot.send_message(m.chat.id, "تم الإلغاء.")
            return

        if text == BTN_BACK_CATS:
            _ask_category(m.chat.id, country_id, country_name)
            return

        if text == BTN_BACK_COUNTRIES:
            _user_country_page[user_id] = 0
            _show_countries_page(m.chat.id, user_id)
            return

        left = text.split("|")[0].strip()
        service_code = _extract_code_from_label(left)
        if not service_code:
            _rescue_menu(m.chat.id, user_id, country_id, country_name, "خدمة غير صالحة.")
            return

        entry = _safe_call(m, catalog_cache.get_service_entry, country_id, service_code)
        if not entry:
            _rescue_menu(
                m.chat.id,
                user_id,
                country_id,
                country_name,
                "هذه الخدمة غير متاحة حالياً في هذه الدولة.\n"
                "اختر (رجوع للفئات) أو (بحث عن خدمة) أو (رجوع للدول)."
            )
            return

        _confirm_service(m, country_id, country_name, service_code, float(entry["sell"]))

    # =========================
    # Confirm & get number
    # =========================
    def _confirm_service(m: Message, country_id: str, country_name: str, service_code: str, price: float):
        user_id = m.from_user.id
        balance = db.get_balance(user_id)

        if balance != -1 and balance < price:
            bot.send_message(m.chat.id, "رصيدك غير كافٍ.")
            _rescue_menu(
                m.chat.id,
                user_id,
                country_id,
                country_name,
                "رصيدك غير كافٍ.\nاختر (رجوع للفئات) أو (رجوع للدول)."
            )
            return

        it = service_catalog_ar.translate_code(service_code)
        service_label = it.ar if it else service_code

        kb = _kb(["موافق"], [BTN_BACK_CATS], [BTN_BACK_COUNTRIES], [BTN_CANCEL])
        bot.send_message(
            m.chat.id,
            f"الدولة: {country_name}\n"
            f"الخدمة: {service_label} ({service_code})\n"
            f"الشبكة: any\n"
            f"السعر: {price}\n\n"
            "هل تريد المتابعة؟",
            reply_markup=kb
        )
        bot.register_next_step_handler(m, confirm_order, country_id, country_name, service_code, price)

    def confirm_order(m: Message, country_id: str, country_name: str, service_code: str, price: float):
        user_id = m.from_user.id
        txt = (m.text or "").strip()

        if txt == BTN_BACK_CATS:
            _ask_category(m.chat.id, country_id, country_name)
            return

        if txt == BTN_BACK_COUNTRIES:
            _user_country_page[user_id] = 0
            _show_countries_page(m.chat.id, user_id)
            return

        if txt != "موافق":
            bot.send_message(m.chat.id, "تم الإلغاء.")
            return

        if _block_if_busy(bot, m, user_id):
            return

        order = state.ActiveOrder(
            user_id=user_id,
            service_name=service_code,
            service_code=service_code,
            price=price,
            country=country_id,
            operator="any",
        )
        state.start_order(order)

        try:
            data = vak_api.get_number(
                api_key=VAK_API_KEY,
                service=service_code,
                country=country_id,
                operator="any",
            )
        except Exception as e:
            state.clear_order(user_id)
            # هنا نتركها بسيطة كما طلبت (بدون ترجمة NO_BALANCE)
            _rescue_menu(
                m.chat.id,
                user_id,
                country_id,
                country_name,
                f"فشل طلب الرقم: {e}\n\nاختر (رجوع للفئات) أو (رجوع للدول)."
            )
            return

        state.set_activation_info(
            user_id,
            activation_id=data["id"],
            phone=data.get("number"),
        )

        kb = _kb(["تحقق من الكود"], ["إلغاء الطلب"])
        bot.send_message(
            m.chat.id,
            f"تم الحصول على الرقم:\n{data.get('number')}\n\n"
            "عند وصول الرسالة اضغط (تحقق من الكود).",
            reply_markup=kb
        )

    # =========================
    # Check code / Cancel
    # =========================
    @bot.message_handler(func=lambda m: m.text == "تحقق من الكود")
    def check_code(m: Message):
        user_id = m.from_user.id
        _ensure_user(user_id)

        order = state.get_active_order(user_id)
        if not order:
            bot.send_message(m.chat.id, "لا يوجد طلب جارٍ.")
            return

        if state.is_expired(user_id, ORDER_TIMEOUT_SECONDS):
            _cancel_order(user_id)
            bot.send_message(m.chat.id, "انتهت المهلة وتم إلغاء الطلب.")
            return

        try:
            res = vak_api.get_status(VAK_API_KEY, order.activation_id)
        except Exception as e:
            bot.send_message(m.chat.id, f"خطأ أثناء الفحص: {e}")
            return

        if res.get("status") == "WAIT":
            bot.send_message(m.chat.id, "لم يصل الكود بعد، حاول لاحقاً.")
            return

        if res.get("status") == "OK":
            code = res.get("code")
            bal = db.get_balance(user_id)
            if bal != -1:
                db.add_balance(user_id, -order.price)

            try:
                vak_api.set_status(VAK_API_KEY, order.activation_id, status=6)
            except Exception:
                pass

            it = service_catalog_ar.translate_code(order.service_code)
            service_label = it.ar if it else order.service_code

            bot.send_message(
                m.chat.id,
                f"✅ كود التفعيل:\n{code}\n\n"
                f"الخدمة: {service_label} ({order.service_code})\n"
                f"تم خصم {order.price} نقطة."
            )
            state.clear_order(user_id)
            return

        bot.send_message(m.chat.id, "حالة غير معروفة.")

    @bot.message_handler(func=lambda m: m.text == "إلغاء الطلب")
    def cancel(m: Message):
        user_id = m.from_user.id
        if not state.has_active_order(user_id):
            bot.send_message(m.chat.id, "لا يوجد طلب لإلغائه.")
            return
        _cancel_order(user_id)
        bot.send_message(m.chat.id, "تم إلغاء الطلب بدون خصم.")

    # =========================
    # Helpers
    # =========================
    def _cancel_order(user_id: int):
        order = state.get_active_order(user_id)
        if order and getattr(order, "activation_id", None):
            try:
                vak_api.set_status(VAK_API_KEY, order.activation_id, status=8)
            except Exception:
                pass
        state.clear_order(user_id)

    def _ensure_user(user_id: int):
        db.register_user(user_id, is_admin=(user_id == ADMIN_USER_ID))

    def _block_if_busy(bot, m: Message, user_id: int) -> bool:
        if state.has_active_order(user_id):
            if state.is_expired(user_id, ORDER_TIMEOUT_SECONDS):
                _cancel_order(user_id)
                return False
            bot.send_message(
                m.chat.id,
                "لديك طلب جارٍ بالفعل.\n"
                "تحقق من الكود أو ألغِ الطلب أولاً."
            )
            return True
        return False