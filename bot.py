import os
import threading
import telebot
import pg8000
from flask import Flask
from telebot.types import LabeledPrice, PreCheckoutQuery

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Online", 200

# Hardcoded directly so Render never misses it
API_TOKEN = "8544070035:AAFt5nlDARbck1zPk_go4Z-LJ_gBM3yHyJo"
bot = telebot.TeleBot(API_TOKEN)

def get_db_connection():
    # Parsing the PostgreSQL URL string components directly for pg8000 compatibility
    return pg8000.connect(
        user="postgres",
        password="postgres:srtlover534@gmail.com",
        host="db.cqpgjiqyvwpnfdtbsrts.supabase.co",
        port=5432,
        database="postgres"
    )

def get_available_account(target_price):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, details FROM cpm2_inventory WHERE price = %s AND status = 'AVAILABLE' LIMIT 1;", 
        (target_price,)
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def mark_as_sold(account_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE cpm2_inventory SET status = 'SOLD' WHERE id = %s;", (account_id,))
    conn.commit()
    cursor.close()
    conn.close()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "👋 Yo! Zenith Garage store bot connection test successful, bro!\n\nUse `/buy_budget` or `/buy_premium` to check live stocks.")

@bot.message_handler(commands=['buy_budget'])
def buy_budget(message):
    try:
        handle_purchase(message, 500, "CPM2 Budget Account")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Database connection error: {str(e)}")

@bot.message_handler(commands=['buy_premium'])
def buy_premium(message):
    try:
        handle_purchase(message, 1000, "CPM2 Premium Account")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Database connection error: {str(e)}")

def handle_purchase(message, price, title):
    try:
        account = get_available_account(price)
        if not account:
            bot.reply_to(message, f"❌ Out of stock for the {title} tier right now, bro!")
            return

        prices = [LabeledPrice(label=title, amount=price)]
        bot.send_invoice(
            chat_id=message.chat.id,
            title=title,
            description="Automatic instant delivery via Telegram Stars.",
            invoice_payload=f"id_{account[0]}_price_{price}",
            provider_token="", 
            currency="XTR",
            prices=prices,
            start_parameter="cpm2-store"
        )
    except Exception as e:
        bot.reply_to(message, f"⚠️ System Error: {str(e)}")

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_validation(pre_checkout_query: PreCheckoutQuery):
    try:
        payload = pre_checkout_query.invoice_payload
        account_id = int(payload.split("_")[1])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM cpm2_inventory WHERE id = %s;", (account_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result and result[0].strip().upper() == 'AVAILABLE':
            bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
        else:
            bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Account sold out right as you clicked!")
    except Exception:
        bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Database checking issue.")

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    try:
        payload = message.successful_payment.invoice_payload
        account_id = int(payload.split("_")[1])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT details FROM cpm2_inventory WHERE id = %s;", (account_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            bot.send_message(message.chat.id, f"⚡ **Payment Confirmed!** Here are your CPM2 credentials:\n\n`{result[0]}`")
            mark_as_sold(account_id)
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Delivery issue, contact support. Details: {str(e)}")

# Added long_polling_timeout to completely mitigate 409 conflict overlaps on hosting environments
threading.Thread(target=bot.infinity_polling, kwargs={'skip_pending': True, 'timeout': 20, 'long_polling_timeout': 5}, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)

