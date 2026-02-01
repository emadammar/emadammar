# handlers_waseena.py
# وصّينا: مطاعم + مولات + نظام سائقين + متاجر + منتجات + طلبات (الدفع عند التسليم)
# بدون تعقيد، وبدون المساس بباقي أجزاء البوت

from telebot import types
from telebot.types import Message

import db
from config import ADMIN_USER_ID


# ===== Buttons =====
BTN_WASEENA = "وصينا"
BTN_BACK = "رجوع"

# User
BTN_REST = "مطاعم"
BTN_MALL = "مولات"
BTN_JOIN_DRIVER = "انضمام كسائق"
BTN_MY_ORDERS = "طلباتي"

# Driver
BTN_ADD_STORE = "إضافة متجر"
BTN_ADD_PRODUCT = "إضافة منتج"
BTN_DRIVER_ORDERS = "طلبات التوصيل"
BTN_MY_STORES = "متاجري"

# Admin
BTN_DRIVER_REQUESTS = "طلبات الانضمام كسائق"
BTN_DRIVERS_LIST = "قائمة السائقين"
BTN_PENDING_STORES = "متاجر بانتظار الموافقة"
BTN_WEEKLY_REPORT = "تقرير أسبوعي"

def _is_admin(user_id: int) -> bool:
    return int(user_id) == int(ADMIN_USER_ID)


def _is_driver(user_id: int) -> bool:
    return db.is_driver_active(int(user_id))


def _kb(rows):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for row in rows:
        if isinstance(row, (list, tuple)):
            kb.row(*[types.KeyboardButton(str(x)) for x in row])
        else:
            kb.add(types.KeyboardButton(str(row)))
    return kb


# سياق بسيط لتفادي تداخل "رجوع" مع أقسام أخرى
_ctx = {}  # user_id -> True/False


def _go_home(bot, m: Message, build_main_keyboard):
    _ctx.pop(m.from_user.id, None)
    if build_main_keyboard is None:
        bot.send_message(m.chat.id, "رجعت للقائمة الرئيسية. استخدم /start.")
        return
    bot.send_message(m.chat.id, "القائمة الرئيسية:", reply_markup=build_main_keyboard(_is_admin(m.from_user.id)))


def _menu_keyboard_for(user_id: int):
    # Admin
    if _is_admin(user_id):
        return _kb([
            [BTN_DRIVER_REQUESTS, BTN_DRIVERS_LIST],
            [BTN_PENDING_STORES, BTN_WEEKLY_REPORT],
            [BTN_BACK],
        ])

    # Driver
    if _is_driver(user_id):
        return _kb([
            [BTN_REST, BTN_MALL],
            [BTN_ADD_STORE, BTN_ADD_PRODUCT],
            [BTN_DRIVER_ORDERS, BTN_MY_STORES],
            [BTN_MY_ORDERS, BTN_BACK],
        ])

    # Normal user
    return _kb([
        [BTN_REST, BTN_MALL],
        [BTN_JOIN_DRIVER, BTN_MY_ORDERS],
        [BTN_BACK],
    ])


def register_waseena_handlers(bot, build_main_keyboard=None):

    # ===== Entry: وصينا =====
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_WASEENA)
    def waseena_entry(m: Message):
        _ctx[m.from_user.id] = True
        bot.send_message(m.chat.id, "وصّينا: اختر خدمة:", reply_markup=_menu_keyboard_for(m.from_user.id))

    # ===== Back (داخل وصينا فقط) =====
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_BACK and _ctx.get(m.from_user.id) is True)
    def waseena_back(m: Message):
        _go_home(bot, m, build_main_keyboard)




    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_WEEKLY_REPORT and _is_admin(m.from_user.id))
    def admin_weekly_report(m: Message):
        _ctx[m.from_user.id] = True

        # نحسب بداية الأسبوع (الإثنين 00:00) حسب توقيت الجهاز
        import datetime
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo("Europe/Berlin")
        except Exception:
            tz = None

        now = datetime.datetime.now(tz=tz) if tz else datetime.datetime.now()
        monday = now - datetime.timedelta(days=now.weekday())
        start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + datetime.timedelta(days=7)

        start_ts = int(start.timestamp())
        end_ts = int(end.timestamp())

        rows = db.weekly_driver_report(start_ts, end_ts)
        if not rows:
            bot.send_message(m.chat.id, "لا يوجد تسليمات مؤكدة هذا الأسبوع.", reply_markup=_menu_keyboard_for(m.from_user.id))
            return

        from config import WASEENA_CURRENCY, WASEENA_BOT_CUT_RATE

        total_profit = 0.0
        total_bot = 0.0
        total_driver = 0.0

        lines = [f"تقرير أسبوعي (نسبة البوت من الربح: {WASEENA_BOT_CUT_RATE*100:.0f}%)"]
        lines.append(f"الفترة: {start.strftime('%Y-%m-%d')} إلى {end.strftime('%Y-%m-%d')}")
        lines.append("")

        for r in rows:
            total_profit += float(r["profit_total"] or 0)
            total_bot += float(r["bot_cut_total"] or 0)
            total_driver += float(r["driver_cut_total"] or 0)

            lines.append(
                f"سائق ID: {r['driver_id']}\n"
                f"- عدد الطلبات: {r['orders_count']}\n"
                f"- إجمالي التحصيل: {float(r['gross_total'] or 0):.2f} {WASEENA_CURRENCY}\n"
                f"- التكلفة الحقيقية: {float(r['real_total'] or 0):.2f} {WASEENA_CURRENCY}\n"
                f"- الربح: {float(r['profit_total'] or 0):.2f} {WASEENA_CURRENCY}\n"
                f"- حصة البوت: {float(r['bot_cut_total'] or 0):.2f} {WASEENA_CURRENCY}\n"
                f"- حصة السائق: {float(r['driver_cut_total'] or 0):.2f} {WASEENA_CURRENCY}\n"
            )

        lines.append("—" * 20)
        lines.append(f"الإجمالي:\n- الربح: {total_profit:.2f} {WASEENA_CURRENCY}\n- حصة البوت: {total_bot:.2f} {WASEENA_CURRENCY}\n- حصة السائقين: {total_driver:.2f} {WASEENA_CURRENCY}")

        bot.send_message(m.chat.id, "\n".join(lines), reply_markup=_menu_keyboard_for(m.from_user.id))





    # =========================================================
    # 1) انضمام كسائق (User -> طلب للأدمن)
    # =========================================================
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_JOIN_DRIVER)
    def join_driver(m: Message):
        _ctx[m.from_user.id] = True
        bot.send_message(m.chat.id, "اكتب ملاحظة قصيرة عنك (مثال: اسمك + منطقتك + رقمك) ثم أرسلها الآن.\n(أرسل 'إلغاء' للإلغاء)")

        def _save_note(mm: Message):
            note = (mm.text or "").strip()
            if not note or note in ("إلغاء", "الغاء"):
                bot.send_message(mm.chat.id, "تم الإلغاء.", reply_markup=_menu_keyboard_for(mm.from_user.id))
                return
            db.request_driver_join(mm.from_user.id, note=note)
            bot.send_message(mm.chat.id, "تم إرسال طلبك للإدارة. سيتم الرد عند الموافقة.", reply_markup=_menu_keyboard_for(mm.from_user.id))

        bot.register_next_step_handler(m, _save_note)

    # =========================================================
    # 2) الأدمن: عرض طلبات الانضمام + قبول/رفض
    # =========================================================
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_DRIVER_REQUESTS and _is_admin(m.from_user.id))
    def admin_driver_requests(m: Message):
        _ctx[m.from_user.id] = True
        reqs = db.list_driver_requests(status="pending")
        if not reqs:
            bot.send_message(m.chat.id, "لا توجد طلبات انضمام حالياً.", reply_markup=_menu_keyboard_for(m.from_user.id))
            return

        bot.send_message(m.chat.id, f"طلبات الانضمام: {len(reqs)}\nسأعرض آخر 10 طلبات.")
        for r in reqs[:10]:
            uid = int(r["user_id"])
            note = (r.get("note") or "").strip()
            mk = types.InlineKeyboardMarkup()
            mk.add(
                types.InlineKeyboardButton("✅ قبول", callback_data=f"wz_drv_ok:{uid}"),
                types.InlineKeyboardButton("❌ رفض", callback_data=f"wz_drv_no:{uid}")
            )
            bot.send_message(m.chat.id, f"ID: {uid}\nملاحظة: {note or '-'}", reply_markup=mk)

    # =========================================================
    # 3) الأدمن: قائمة السائقين + حظر
    # =========================================================
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_DRIVERS_LIST and _is_admin(m.from_user.id))
    def admin_drivers_list(m: Message):
        _ctx[m.from_user.id] = True
        drivers = db.list_drivers(status="active")
        if not drivers:
            bot.send_message(m.chat.id, "لا يوجد سائقين فعالين.", reply_markup=_menu_keyboard_for(m.from_user.id))
            return

        bot.send_message(m.chat.id, f"السائقين الفعالين: {len(drivers)}\nسأعرض آخر 10.")
        for d in drivers[:10]:
            uid = int(d["user_id"])
            mk = types.InlineKeyboardMarkup()
            mk.add(types.InlineKeyboardButton("⛔ حظر", callback_data=f"wz_drv_block:{uid}"))
            bot.send_message(m.chat.id, f"سائق ID: {uid}", reply_markup=mk)

    # =========================================================
    # 4) السائق: إضافة متجر (مطعم/مول) - يحتاج موافقة أدمن
    # =========================================================
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_ADD_STORE and _is_driver(m.from_user.id))
    def driver_add_store(m: Message):
        _ctx[m.from_user.id] = True

        kb = _kb([["مطعم", "مول"], [BTN_BACK]])
        bot.send_message(m.chat.id, "اختر نوع المتجر:", reply_markup=kb)

        def _pick_type(mm: Message):
            t = (mm.text or "").strip()
            if t == BTN_BACK:
                bot.send_message(mm.chat.id, "رجوع.", reply_markup=_menu_keyboard_for(mm.from_user.id))
                return
            if t not in ("مطعم", "مول"):
                bot.send_message(mm.chat.id, "اختيار غير صحيح. اختر (مطعم) أو (مول).")
                bot.register_next_step_handler(mm, _pick_type)
                return

            store_type = "restaurant" if t == "مطعم" else "mall"
            bot.send_message(mm.chat.id, "اكتب اسم المتجر الآن:")

            def _save_name(mmm: Message):
                name = (mmm.text or "").strip()
                if not name or name in ("إلغاء", "الغاء"):
                    bot.send_message(mmm.chat.id, "تم الإلغاء.", reply_markup=_menu_keyboard_for(mmm.from_user.id))
                    return
                store_id = db.add_store(store_type, name, owner_driver_id=mmm.from_user.id)
                bot.send_message(
                    mmm.chat.id,
                    f"تم إضافة المتجر ✅ (رقم: {store_id})\nالحالة: بانتظار موافقة الإدارة.",
                    reply_markup=_menu_keyboard_for(mmm.from_user.id)
                )

            bot.register_next_step_handler(mm, _save_name)

        bot.register_next_step_handler(m, _pick_type)

    # =========================================================
    # 5) الأدمن: متاجر بانتظار الموافقة
    # =========================================================
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_PENDING_STORES and _is_admin(m.from_user.id))
    def admin_pending_stores(m: Message):
        _ctx[m.from_user.id] = True
        stores = db.list_pending_stores(limit=20)
        if not stores:
            bot.send_message(m.chat.id, "لا توجد متاجر بانتظار الموافقة.", reply_markup=_menu_keyboard_for(m.from_user.id))
            return

        bot.send_message(m.chat.id, f"متاجر بانتظار الموافقة: {len(stores)}")
        for s in stores[:10]:
            sid = int(s["id"])
            stype = s.get("type")
            name = s.get("name")
            owner = int(s.get("owner_driver_id") or 0)
            mk = types.InlineKeyboardMarkup()
            mk.add(
                types.InlineKeyboardButton("✅ تفعيل", callback_data=f"wz_store_ok:{sid}"),
                types.InlineKeyboardButton("⛔ حظر", callback_data=f"wz_store_block:{sid}")
            )
            bot.send_message(m.chat.id, f"#{sid} | {name}\nنوع: {stype}\nسائق: {owner}", reply_markup=mk)

    # =========================================================
    # 6) السائق: إضافة منتج (يختار متجر من متاجره الفعّالة فقط)
    # =========================================================
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_ADD_PRODUCT and _is_driver(m.from_user.id))
    def driver_add_product(m: Message):
        _ctx[m.from_user.id] = True

        # نجلب متاجر السائق الفعّالة فقط
        my_rest = [x for x in db.list_driver_stores(m.from_user.id, "restaurant") if x.get("status") == "active"]
        my_mall = [x for x in db.list_driver_stores(m.from_user.id, "mall") if x.get("status") == "active"]

        if not my_rest and not my_mall:
            bot.send_message(
                m.chat.id,
                "لا يوجد لديك متاجر فعّالة حالياً.\nأضف متجر أولاً وانتظر موافقة الإدارة.",
                reply_markup=_menu_keyboard_for(m.from_user.id)
            )
            return

        mk = types.InlineKeyboardMarkup()
        for s in (my_rest + my_mall)[:30]:
            sid = int(s["id"])
            mk.add(types.InlineKeyboardButton(f"#{sid} - {s['name']}", callback_data=f"wz_pick_store:{sid}"))
        bot.send_message(m.chat.id, "اختر المتجر لإضافة منتج:", reply_markup=mk)

    # =========================================================
    # 7) المستخدم: عرض متاجر/منتجات + إنشاء طلب (الدفع عند التسليم)
    # =========================================================
    @bot.message_handler(func=lambda m: (m.text or "").strip() in (BTN_REST, BTN_MALL))
    def user_browse(m: Message):
        _ctx[m.from_user.id] = True
        t = (m.text or "").strip()
        store_type = "restaurant" if t == BTN_REST else "mall"
        stores = db.list_stores(store_type, status="active")
        if not stores:
            bot.send_message(m.chat.id, "لا توجد متاجر حالياً.", reply_markup=_menu_keyboard_for(m.from_user.id))
            return

        mk = types.InlineKeyboardMarkup()
        for s in stores[:40]:
            sid = int(s["id"])
            mk.add(types.InlineKeyboardButton(s["name"], callback_data=f"wz_user_store:{sid}"))
        bot.send_message(m.chat.id, f"اختر {t}:", reply_markup=mk)

    # =========================================================
    # 8) طلباتي (للمستخدم/السائق أيضاً)
    # =========================================================
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_MY_ORDERS)
    def my_orders(m: Message):
        _ctx[m.from_user.id] = True
        orders = db.list_user_orders(m.from_user.id, limit=10)
        if not orders:
            bot.send_message(m.chat.id, "لا يوجد لديك طلبات.", reply_markup=_menu_keyboard_for(m.from_user.id))
            return

        lines = []
        for o in orders:
            lines.append(f"#{o['id']} | الحالة: {o['status']} | كمية: {o['qty']}")
        bot.send_message(m.chat.id, "آخر طلباتك:\n" + "\n".join(lines), reply_markup=_menu_keyboard_for(m.from_user.id))

    # =========================================================
    # 9) طلبات التوصيل (للسائق) + زر حجز
    # =========================================================
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_DRIVER_ORDERS and _is_driver(m.from_user.id))
    def driver_orders(m: Message):
        _ctx[m.from_user.id] = True
        orders = db.list_pending_orders(limit=10)
        if not orders:
            bot.send_message(m.chat.id, "لا توجد طلبات جديدة حالياً.", reply_markup=_menu_keyboard_for(m.from_user.id))
            return

        bot.send_message(m.chat.id, f"طلبات جديدة: {len(orders)} (أعرض آخر 10)")
        for o in orders:
            oid = int(o["id"])
            mk = types.InlineKeyboardMarkup()
            mk.add(types.InlineKeyboardButton("✅ حجز الطلب", callback_data=f"wz_order_accept:{oid}"))
            bot.send_message(m.chat.id, f"طلب #{oid}\nزبون ID: {o['user_id']}\nالعنوان: {o['address_text']}", reply_markup=mk)

    # =========================================================
    # 10) Callbacks
    # =========================================================
    @bot.callback_query_handler(func=lambda call: (call.data or "").startswith("wz_"))
    def waseena_callbacks(call):
        data = (call.data or "")
        uid = call.from_user.id
        cid = call.message.chat.id

        # --- Admin approve/reject driver ---
        if data.startswith("wz_drv_ok:") and _is_admin(uid):
            target = int(data.split(":", 1)[1])
            db.approve_driver(target)
            bot.answer_callback_query(call.id, "تم قبول السائق ✅", show_alert=True)
            bot.send_message(cid, f"تم تفعيل السائق: {target}")

        elif data.startswith("wz_drv_no:") and _is_admin(uid):
            target = int(data.split(":", 1)[1])
            db.reject_driver(target)
            bot.answer_callback_query(call.id, "تم رفض الطلب ❌", show_alert=True)
            bot.send_message(cid, f"تم رفض السائق: {target}")

        elif data.startswith("wz_drv_block:") and _is_admin(uid):
            target = int(data.split(":", 1)[1])
            db.block_driver(target)
            bot.answer_callback_query(call.id, "تم حظر السائق ⛔", show_alert=True)
            bot.send_message(cid, f"تم حظر السائق: {target}")

        # --- Admin approve/block store ---
        elif data.startswith("wz_store_ok:") and _is_admin(uid):
            sid = int(data.split(":", 1)[1])
            db.approve_store(sid)
            bot.answer_callback_query(call.id, "تم تفعيل المتجر ✅", show_alert=True)

        elif data.startswith("wz_store_block:") and _is_admin(uid):
            sid = int(data.split(":", 1)[1])
            db.block_store(sid)
            bot.answer_callback_query(call.id, "تم حظر المتجر ⛔", show_alert=True)

        # --- Driver pick store to add product ---
        elif data.startswith("wz_pick_store:") and _is_driver(uid):
            sid = int(data.split(":", 1)[1])
            store = db.get_store(sid)
            if not store or int(store.get("owner_driver_id", 0)) != int(uid) or store.get("status") != "active":
                bot.answer_callback_query(call.id, "لا يمكنك الإضافة لهذا المتجر.", show_alert=True)
                return

            bot.answer_callback_query(call.id, "أدخل اسم المنتج الآن.")
            bot.send_message(cid, f"متجر: {store['name']}\nأرسل اسم المنتج:")

            def _step_name(m: Message):
                name = (m.text or "").strip()
                if not name or name in ("إلغاء", "الغاء"):
                    bot.send_message(m.chat.id, "تم الإلغاء.", reply_markup=_menu_keyboard_for(m.from_user.id))
                    return

                bot.send_message(m.chat.id, "أرسل السعر الحقيقي (مثال: 85):")

                def _step_real(mm: Message):
                    try:
                        real_price = float((mm.text or "").strip())
                        if real_price <= 0:
                            raise ValueError()
                    except Exception:
                        bot.send_message(mm.chat.id, "رقم غير صحيح. أرسل السعر الحقيقي كرقم فقط (مثال 85).")
                        bot.register_next_step_handler(mm, _step_real)
                        return

                    bot.send_message(mm.chat.id, "أرسل سعر التسليم للزبون (السعر النهائي) (مثال: 100):")

                    def _step_final(mmm: Message):
                        try:
                            final_price = float((mmm.text or "").strip())
                            if final_price <= 0:
                                raise ValueError()
                        except Exception:
                            bot.send_message(mmm.chat.id, "رقم غير صحيح. أرسل السعر النهائي كرقم فقط (مثال 100).")
                            bot.register_next_step_handler(mmm, _step_final)
                            return

                        if final_price < real_price:
                            bot.send_message(mmm.chat.id, "السعر النهائي يجب أن يكون أكبر أو يساوي السعر الحقيقي.")
                            bot.register_next_step_handler(mmm, _step_final)
                            return

                        pid = db.add_product(sid, driver_id=uid, name=name, real_price=real_price, final_price=final_price)
                        profit = final_price - real_price
                        bot.send_message(
                            mmm.chat.id,
                            f"تمت إضافة المنتج ✅\nID المنتج: {pid}\nالمنتج: {name}\nحقيقي: {real_price}\nنهائي: {final_price}\nربح: {profit}",
                            reply_markup=_menu_keyboard_for(mmm.from_user.id)
                        )

                    bot.register_next_step_handler(mm, _step_final)

                bot.register_next_step_handler(m, _step_real)

            bot.register_next_step_handler(call.message, _step_name)

        # --- User confirms received ---
        elif data.startswith("wz_user_received:"):
            oid = int(data.split(":", 1)[1])

            # إذا عندك دالة التأكيد في db استخدمها، وإلا سنضيفها لاحقاً
            try:
                from config import WASEENA_BOT_CUT_RATE
                ok = db.confirm_order_delivered_by_user(order_id=oid, user_id=uid, bot_cut_rate=float(WASEENA_BOT_CUT_RATE))
            except Exception:
                ok = False

            if not ok:
                bot.answer_callback_query(call.id, "لا يمكن تأكيد هذا الطلب الآن.", show_alert=True)
                return

            bot.answer_callback_query(call.id, "تم تأكيد الاستلام ✅", show_alert=True)
            bot.send_message(cid, f"تم تأكيد استلام الطلب #{oid} ✅ شكراً لك.")

            order = db.get_order(oid)
            if order:
                try:
                    bot.send_message(int(order["driver_id"]), f"الزبون أكد استلام الطلب #{oid} ✅")
                except Exception:
                    pass

        # --- User picks store to view products ---
        elif data.startswith("wz_user_store:"):
            sid = int(data.split(":", 1)[1])

            store = db.get_store(sid)
            if not store or store.get("status") != "active":
                bot.answer_callback_query(call.id, "المتجر غير متاح.", show_alert=True)
                return

            prods = db.list_products(sid, only_active=True) or []
            if not prods:
                bot.answer_callback_query(call.id, "لا توجد منتجات حالياً.", show_alert=True)
                return

            mk = types.InlineKeyboardMarkup(row_width=1)
            for p in prods[:40]:
                name = str(p.get("name", "")).strip()[:40]
                price = p.get("final_price", 0)
                mk.add(types.InlineKeyboardButton(
                    f"{name} - {price} ليرة",
                    callback_data=f"wz_user_prod:{sid}:{p['id']}"
                ))

            bot.answer_callback_query(call.id, "اختر منتجاً.")
            bot.send_message(cid, f"متجر: {store['name']}\nاختر منتج:", reply_markup=mk)

        # --- User picks product to order ---
        elif data.startswith("wz_user_prod:"):
            parts = data.split(":")
            sid = int(parts[1])
            pid = int(parts[2])

            store = db.get_store(sid)
            prod = db.get_product(pid)

            if not store or store.get("status") != "active" or not prod or int(prod.get("is_active", 1)) != 1:
                bot.answer_callback_query(call.id, "هذا الخيار غير متاح.", show_alert=True)
                return

            bot.answer_callback_query(call.id, "أرسل الكمية.")
            bot.send_message(
                cid,
                f"طلب المنتج: {prod['name']}\nالسعر النهائي: {prod['final_price']} ليرة\nأرسل الكمية (رقم):"
            )

            def _qty_step(m: Message):
                try:
                    qty = int((m.text or "").strip())
                    if qty <= 0:
                        raise ValueError()
                except Exception:
                    bot.send_message(m.chat.id, "الكمية غير صحيحة. أرسل رقم (مثال 1).")
                    bot.register_next_step_handler(m, _qty_step)
                    return

                bot.send_message(m.chat.id, "أرسل العنوان/المكان بالتفصيل:")

                def _addr_step(mm: Message):
                    addr = (mm.text or "").strip()
                    if not addr or addr in ("إلغاء", "الغاء"):
                        bot.send_message(mm.chat.id, "تم الإلغاء.", reply_markup=_menu_keyboard_for(mm.from_user.id))
                        return

                    # توافق مع أي نسخة من create_order (قد تكون قد عدلتها)
                    try:
                        oid = db.create_order(
                            user_id=mm.from_user.id,
                            store_id=sid,
                            product_id=pid,
                            qty=qty,
                            address_text=addr,
                            real_price=float(prod.get("real_price", 0)),
                            final_price=float(prod.get("final_price", 0)),
                        )
                    except TypeError:
                        oid = db.create_order(mm.from_user.id, sid, pid, qty, addr)

                    bot.send_message(
                        mm.chat.id,
                        f"تم إنشاء الطلب ✅ رقم #{oid}\nالدفع عند التسليم.\nسيظهر للسائقين للحجز.",
                        reply_markup=_menu_keyboard_for(mm.from_user.id)
                    )

                bot.register_next_step_handler(m, _addr_step)

            bot.register_next_step_handler(call.message, _qty_step)

        # --- Driver accept order ---
        elif data.startswith("wz_order_accept:") and _is_driver(uid):
            oid = int(data.split(":", 1)[1])
            
            if db.driver_is_busy(uid):
                bot.answer_callback_query(
                    call.id,
                    "أنت مشغول حالياً بطلب آخر. أنهِه أولاً ثم احجز طلب جديد.",
                    show_alert=True

                )
                return
            ok = db.accept_order(oid, driver_id=uid)
            if not ok:
                bot.answer_callback_query(call.id, "تم حجزه من قبل أو لم يعد متاحاً.", 
                show_alert=True
                
                )
                return
                
            bot.answer_callback_query(call.id, "تم حجز الطلب ✅", show_alert=True)
            
            
            order = db.get_order(oid)
            if order:
                mk = types.InlineKeyboardMarkup()
                mk.add(types.InlineKeyboardButton("✅ استلمت", callback_data=
                f"wz_user_received:{oid}"))
            
                try:
                    bot.send_message(
                        int(order["user_id"]),
                        f"تم قبول طلبك رقم #{oid} من السائق ID: {uid}\nالدفع عند التسليم.\n\nعند استلام الطلب اضغط: (استلمت)",
                        reply_markup=mk
                        
                    )
                except Exception:
                    pass
         
            

        else:
            bot.answer_callback_query(call.id, "غير مسموح.", show_alert=True)

    # =========================================================
    # 11) متاجري (للسائق)
    # =========================================================
    @bot.message_handler(func=lambda m: (m.text or "").strip() == BTN_MY_STORES and _is_driver(m.from_user.id))
    def my_stores(m: Message):
        _ctx[m.from_user.id] = True
        stores = db.list_driver_stores(m.from_user.id)
        if not stores:
            bot.send_message(m.chat.id, "لا يوجد لديك متاجر.", reply_markup=_menu_keyboard_for(m.from_user.id))
            return
        lines = []
        for s in stores[:20]:
            lines.append(f"#{s['id']} | {s['name']} | {s['type']} | الحالة: {s['status']}")
        bot.send_message(m.chat.id, "متاجرك:\n" + "\n".join(lines), reply_markup=_menu_keyboard_for(m.from_user.id))