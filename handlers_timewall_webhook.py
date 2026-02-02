# handlers_timewall_webhook.py
# استقبال Postback من TimeWall (بدون حماية – مرحلة أولى)

from flask import request
from main import app
import db


@app.route("/postback", methods=["GET"])
def timewall_postback():
    try:
        # قراءة البيانات القادمة من TimeWall
        user_id = request.args.get("userID")
        currency_amount = request.args.get("currencyAmount")
        transaction_id = request.args.get("transactionID")
        pb_type = request.args.get("type", "credit")

        # تحقق أساسي
        if not user_id or not currency_amount or not transaction_id:
            # نرجع 200 حتى لا يعيد TimeWall الإرسال
            return "OK", 200

        user_id = int(user_id)
        currency_amount = int(float(currency_amount))  # احتياط لو جاء رقم عشري

        # منع التكرار
        if db.is_transaction_exists(transaction_id):
            return "OK", 200

        # إضافة / خصم النقاط
        if currency_amount != 0:
            db.add_points(user_id, currency_amount)

        # تسجيل العملية
        db.log_transaction(
            transaction_id=transaction_id,
            user_id=user_id,
            amount=currency_amount,
            source="timewall",
            type=pb_type
        )

        return "OK", 200

    except Exception as e:
        # لا نعيد خطأ أبداً
        print("TimeWall Postback Error:", e)
        return "OK", 200