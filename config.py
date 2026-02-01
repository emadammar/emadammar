# config.py
# إعدادات البوت (متوافق 100% مع Pydroid3 + Termux)
# المزود الحالي: smscenter.pro

# ========= Telegram =========
BOT_TOKEN = "8459544189:AAFPfZBHCEYq632vI332F6n6z0LMTBspn0w"
ADMIN_USER_ID = 8327957313  # رقم الأدمن (int)

# ========= SMSCENTER API =========
# ملاحظة: أبقينا اسم المتغير VAK_API_KEY لتفادي كسر الاستيراد في بقية الملفات
VAK_API_KEY = "0b6c9a77646e49fe9284cf455429bb8a"

# ========= Defaults / تشغيل =========
POLLING_TIMEOUT = 60
LONG_POLLING_TIMEOUT = 60

# ========= سياسة التشغيل =========
ONE_ACTIVE_ORDER_PER_USER = True      # طلب واحد فقط لكل مستخدم
CHARGE_ON_SMS_ONLY = True             # الخصم فقط عند وصول الكود
ORDER_TIMEOUT_SECONDS = 20 * 60       # مدة صلاحية الطلب (20 دقيقة) قبل الإلغاء التلقائي

# ========= افتراضات مزود (Fallback) =========
# سيتم استبدالها فعلياً باختيار الدولة من المستخدم في الإضافة A
DEFAULT_COUNTRY = "ru"
DEFAULT_OPERATOR = ""  # اتركها فارغة إذا ليست مطلوبة

# ========= Addition A: Pricing & Catalog =========
# نسبة الربح (50%)
PROFIT_RATE = 0.50


# ========= Temp Email (mail.tm) =========
TEMP_EMAIL_PRICE = 1           # سعر الإيميل المؤقت بالنقاط
TEMP_EMAIL_PAID = True         # True = مدفوع / False = مجاني
TEMP_EMAIL_SHOW_LIMIT = 3      # كم رسالة نعرض عند التحديث

# وصّينا
WASEENA_BOT_CUT_RATE = 0.10   # نسبة البوت من "الربح" فقط (مثال 10%)
WASEENA_CURRENCY = "ليرة"     # للعرض فقط

REFERRAL_REWARD = 0.1  # عدد النقاط لكل إحالة


# تحديث الأسعار من الموقع كل 30 دقيقة
PRICES_CACHE_TTL_SECONDS = 30 * 60