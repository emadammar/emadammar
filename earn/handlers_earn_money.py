# earn/handlers_earn_money.py
# زر "💰 ربح المال" -> (مواقع) + إدارة للأدمن (إضافة/تعديل/حذف)

from telebot import types
from telebot.types import Message

from config import ADMIN_USER_ID
from . import sites_db

BTN_EARN_MONEY = "💰 ربح المال"
BTN_BACK = "↩️ رجوع"
BTN_SITES = "📌 مواقع"

BTN_ADD_SECTION = "➕ إضافة قسم"
BTN_ADD_SITE = "➕ إضافة موقع"
BTN_EDIT_SITE = "📝 تعديل موقع"
BTN_DELETE_SITE = "🗑️ حذف موقع"

# أكواد قصيرة للـ callback (أفضل من نصوص الأزرار)
ACT_EDIT = "edit"
ACT_DEL = "del"

_ctx = {}  # user_id -> داخل ربح المال؟


def _is_admin(user_id: int) -> bool:
    return int(user_id) == int(ADMIN_USER_ID)


def _kb(rows):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for row in rows:
        if isinstance(row, (list, tuple)):
            kb.row(*[types.KeyboardButton(str(x)) for x in row])
        else:
            kb.add(types.KeyboardButton(str(row)))
    return kb


def _earn_money_menu(user_id: int):
    if _is_admin(user_id):
        return _kb([
            [BTN_SITES],
            [BTN_ADD_SECTION, BTN_ADD_SITE],
            [BTN_EDIT_SITE, BTN_DELETE_SITE],
            [BTN_BACK],
        ])
    return _kb([
        [BTN_SITES],
        [BTN_BACK],
    ])


def _go_home(bot, m: Message, build_main_keyboard):
    _ctx.pop(m.from_user.id, None)
    if build_main_keyboard is None:
        bot.send_message(m.chat.id, "رجعت للقائمة الرئيسية. استخدم /start.")
        return
    bot.send_message(
        m.chat.id,
        "القائمة الرئيسية:",
        reply_markup=build_main_keyboard(_is_admin(m.from_user.id))
    )


def register_earn_money_handlers(bot, build_main_keyboard=None):
    try:
        sites_db.init_sites_db()
    except Exception:
        pass

    # دخول
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_EARN_MONEY)
    def enter(m: Message):
        _ctx[m.from_user.id] = True
        bot.send_message(
            m.chat.id,
            "يمكنك الربح من خلال تنفيذ مهام بسيطة في مواقع خارجية.\n"
            "اختر موقعاً، ادخل عبر الرابط، ونفّذ المطلوب حسب الشروط.\n\n"
            "✅ تنفيذ صحيح = مكافأة\n"
            "✅ كل موقع له شروطه الخاصة\n"
            "👇 اختر الموقع وابدأ:",
            reply_markup=_earn_money_menu(m.from_user.id)
        )

    # رجوع
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_BACK and _ctx.get(m.from_user.id) is True)
    def back(m: Message):
        _go_home(bot, m, build_main_keyboard)

    # مواقع -> أقسام
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_SITES and _ctx.get(m.from_user.id) is True)
    def show_sections(m: Message):
        sections = sites_db.list_sections(active_only=True, limit=50)
        if not sections:
            bot.send_message(m.chat.id, "لا توجد أقسام بعد. الإدارة تحتاج إضافة قسم أولاً.", reply_markup=_earn_money_menu(m.from_user.id))
            return

        mk = types.InlineKeyboardMarkup(row_width=1)
        for s in sections[:40]:
            mk.add(types.InlineKeyboardButton(s["name"], callback_data=f"sites_sec:{s['id']}"))
        bot.send_message(m.chat.id, "اختر القسم:", reply_markup=mk)

    # ===== Admin: إضافة قسم =====
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_ADD_SECTION and _is_admin(m.from_user.id))
    def admin_add_section(m: Message):
        bot.send_message(m.chat.id, "أرسل اسم القسم الجديد الآن:")

        def _step(mm: Message):
            name = (mm.text or "").strip()
            if not name or name in ("إلغاء", "الغاء"):
                bot.send_message(mm.chat.id, "تم الإلغاء.", reply_markup=_earn_money_menu(mm.from_user.id))
                return
            try:
                sid = sites_db.add_section(name)
                bot.send_message(mm.chat.id, f"تم إضافة القسم ✅\n#{sid} - {name}", reply_markup=_earn_money_menu(mm.from_user.id))
            except Exception as e:
                bot.send_message(mm.chat.id, f"فشل إضافة القسم.\nسبب: {e}", reply_markup=_earn_money_menu(mm.from_user.id))

        bot.register_next_step_handler(m, _step)

    # ===== Admin: إضافة موقع =====
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_ADD_SITE and _is_admin(m.from_user.id))
    def admin_add_site(m: Message):
        sections = sites_db.list_sections(active_only=True, limit=50)
        if not sections:
            bot.send_message(m.chat.id, "لا يوجد أقسام. أضف قسم أولاً.", reply_markup=_earn_money_menu(m.from_user.id))
            return

        mk = types.InlineKeyboardMarkup(row_width=1)
        for s in sections[:40]:
            mk.add(types.InlineKeyboardButton(s["name"], callback_data=f"admin_add_site_sec:{s['id']}"))
        bot.send_message(m.chat.id, "اختر القسم الذي ستضيف داخله الموقع:", reply_markup=mk)

    # ===== Admin: تعديل/حذف (يختار قسم -> موقع) =====
    @bot.message_handler(func=lambda m: (m.text or "").strip() in (BTN_EDIT_SITE, BTN_DELETE_SITE) and _is_admin(m.from_user.id))
    def admin_choose_site_action(m: Message):
        btn = (m.text or "").strip()
        action = ACT_EDIT if btn == BTN_EDIT_SITE else ACT_DEL

        sections = sites_db.list_sections(active_only=True, limit=50)
        if not sections:
            bot.send_message(m.chat.id, "لا يوجد أقسام.", reply_markup=_earn_money_menu(m.from_user.id))
            return

        mk = types.InlineKeyboardMarkup(row_width=1)
        for s in sections[:40]:
            mk.add(types.InlineKeyboardButton(s["name"], callback_data=f"admin_act_sec:{action}:{s['id']}"))
        bot.send_message(m.chat.id, "اختر القسم أولاً:", reply_markup=mk)

    # ===== Callbacks =====
    @bot.callback_query_handler(func=lambda call: (call.data or "").startswith(("sites_", "admin_")))
    def callbacks(call):
        data = call.data or ""
        cid = call.message.chat.id
        uid = call.from_user.id

        # User: اختر قسم -> مواقع
        if data.startswith("sites_sec:"):
            sec_id = int(data.split(":", 1)[1])
            sec = sites_db.get_section(sec_id)
            if not sec or int(sec.get("is_active", 1)) != 1:
                bot.answer_callback_query(call.id, "القسم غير متاح.", show_alert=True)
                return

            sites = sites_db.list_sites_by_section(sec_id, active_only=True, limit=50)
            if not sites:
                bot.answer_callback_query(call.id, "لا توجد مواقع داخل هذا القسم.", show_alert=True)
                return

            mk = types.InlineKeyboardMarkup(row_width=1)
            for s in sites[:40]:
                mk.add(types.InlineKeyboardButton(s["name"], callback_data=f"sites_open:{s['id']}"))

            bot.answer_callback_query(call.id, "اختر موقعاً.")
            bot.send_message(cid, f"القسم: {sec['name']}\nاختر الموقع:", reply_markup=mk)
            return

        # User: فتح موقع (✅ زر يفتح الرابط)
        if data.startswith("sites_open:"):
            site_id = int(data.split(":", 1)[1])
            site = sites_db.get_site(site_id)
            if not site or int(site.get("is_active", 1)) != 1:
                bot.answer_callback_query(call.id, "الموقع غير متاح.", show_alert=True)
                return

            bot.answer_callback_query(call.id, "تم.")
            text = f"اسم الموقع: {site['name']}\n"

            desc = (site.get("description") or "").strip()
            terms = (site.get("terms") or "").strip()
            if desc:
                text += f"\nالوصف:\n{desc}\n"
            if terms:
                text += f"\nالشروط:\n{terms}\n"

            mk = types.InlineKeyboardMarkup(row_width=1)
            mk.add(types.InlineKeyboardButton("🌐 فتح الموقع", url=str(site["url"])))

            bot.send_message(cid, text, reply_markup=mk)
            return

        # Admin: اختيار قسم لإضافة موقع
        if data.startswith("admin_add_site_sec:") and _is_admin(uid):
            sec_id = int(data.split(":", 1)[1])
            sec = sites_db.get_section(sec_id)
            if not sec or int(sec.get("is_active", 1)) != 1:
                bot.answer_callback_query(call.id, "القسم غير متاح.", show_alert=True)
                return

            bot.answer_callback_query(call.id, "أرسل اسم الموقع.")
            bot.send_message(cid, f"القسم: {sec['name']}\nأرسل اسم الموقع:")

            def _name_step(m: Message):
                name = (m.text or "").strip()
                if not name or name in ("إلغاء", "الغاء"):
                    bot.send_message(m.chat.id, "تم الإلغاء.", reply_markup=_earn_money_menu(m.from_user.id))
                    return

                bot.send_message(m.chat.id, "أرسل رابط الموقع:")

                def _url_step(mm: Message):
                    url = (mm.text or "").strip()
                    if not url or url in ("إلغاء", "الغاء"):
                        bot.send_message(mm.chat.id, "تم الإلغاء.", reply_markup=_earn_money_menu(mm.from_user.id))
                        return

                    bot.send_message(mm.chat.id, "أرسل وصف مختصر (أو اكتب - لتجاهله):")

                    def _desc_step(mmm: Message):
                        desc = (mmm.text or "").strip()
                        if desc == "-":
                            desc = ""

                        bot.send_message(mmm.chat.id, "أرسل الشروط (أو اكتب - لتجاهله):")

                        def _terms_step(mmmm: Message):
                            terms = (mmmm.text or "").strip()
                            if terms == "-":
                                terms = ""
                            try:
                                site_id2 = sites_db.add_site(sec_id, name, url, desc, terms)
                                bot.send_message(
                                    mmmm.chat.id,
                                    f"تم إضافة الموقع ✅\n"
                                    f"- القسم: {sec['name']}\n"
                                    f"- الموقع: {name}\n"
                                    f"- ID: {site_id2}",
                                    reply_markup=_earn_money_menu(mmmm.from_user.id)
                                )
                            except Exception as e:
                                bot.send_message(mmmm.chat.id, f"فشل إضافة الموقع.\nسبب: {e}", reply_markup=_earn_money_menu(mmmm.from_user.id))

                        bot.register_next_step_handler(mmm, _terms_step)

                    bot.register_next_step_handler(mm, _desc_step)

                bot.register_next_step_handler(m, _url_step)

            bot.register_next_step_handler(call.message, _name_step)
            return

        # Admin: اختيار قسم لتعديل/حذف
        if data.startswith("admin_act_sec:") and _is_admin(uid):
            # admin_act_sec:<action>:<sec_id>
            _, action, sec_id_str = data.split(":", 2)
            sec_id = int(sec_id_str)
            sec = sites_db.get_section(sec_id)
            if not sec or int(sec.get("is_active", 1)) != 1:
                bot.answer_callback_query(call.id, "القسم غير متاح.", show_alert=True)
                return

            sites = sites_db.list_sites_by_section(sec_id, active_only=True, limit=50)
            if not sites:
                bot.answer_callback_query(call.id, "لا توجد مواقع داخل هذا القسم.", show_alert=True)
                return

            mk = types.InlineKeyboardMarkup(row_width=1)
            for s in sites[:40]:
                mk.add(types.InlineKeyboardButton(s["name"], callback_data=f"admin_act_site:{action}:{s['id']}"))

            bot.answer_callback_query(call.id, "اختر موقعاً.")
            bot.send_message(cid, f"القسم: {sec['name']}\nاختر الموقع:", reply_markup=mk)
            return

        # Admin: تنفيذ تعديل/حذف على موقع
        if data.startswith("admin_act_site:") and _is_admin(uid):
            _, action, site_id_str = data.split(":", 2)
            site_id = int(site_id_str)
            site = sites_db.get_site(site_id)
            if not site or int(site.get("is_active", 1)) != 1:
                bot.answer_callback_query(call.id, "الموقع غير متاح.", show_alert=True)
                return

            if action == ACT_DEL:
                sites_db.deactivate_site(site_id)
                bot.answer_callback_query(call.id, "تم الحذف ✅")
                bot.send_message(cid, f"تم حذف (تعطيل) الموقع ✅\n{site['name']}", reply_markup=_earn_money_menu(uid))
                return

            if action == ACT_EDIT:
                bot.answer_callback_query(call.id, "أرسل الاسم الجديد (أو اكتب - للإبقاء):")
                bot.send_message(cid, f"تعديل الموقع: {site['name']}\nأرسل الاسم الجديد (أو -):")

                def _edit_name(m: Message):
                    new_name = (m.text or "").strip()
                    if new_name == "-" or not new_name:
                        new_name = site["name"]

                    bot.send_message(m.chat.id, "أرسل الرابط الجديد (أو -):")

                    def _edit_url(mm: Message):
                        new_url = (mm.text or "").strip()
                        if new_url == "-" or not new_url:
                            new_url = site["url"]

                        bot.send_message(mm.chat.id, "أرسل الوصف الجديد (أو -):")

                        def _edit_desc(mmm: Message):
                            new_desc = (mmm.text or "").strip()
                            if new_desc == "-":
                                new_desc = site.get("description") or ""

                            bot.send_message(mmm.chat.id, "أرسل الشروط الجديدة (أو -):")

                            def _edit_terms(mmmm: Message):
                                new_terms = (mmmm.text or "").strip()
                                if new_terms == "-":
                                    new_terms = site.get("terms") or ""

                                try:
                                    sites_db.update_site(site_id, new_name, new_url, new_desc, new_terms)
                                    bot.send_message(mmmm.chat.id, "تم التعديل ✅", reply_markup=_earn_money_menu(mmmm.from_user.id))
                                except Exception as e:
                                    bot.send_message(mmmm.chat.id, f"فشل التعديل.\nسبب: {e}", reply_markup=_earn_money_menu(mmmm.from_user.id))

                            bot.register_next_step_handler(mmm, _edit_terms)

                        bot.register_next_step_handler(mm, _edit_desc)

                    bot.register_next_step_handler(m, _edit_url)

                bot.register_next_step_handler(call.message, _edit_name)
                return

        bot.answer_callback_query(call.id, "غير مسموح.", show_alert=True)