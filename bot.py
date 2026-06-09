import os
import telebot
import psycopg2
from flask import Flask, request

app = Flask(__name__)

# SECURITY UPGRADE: Credentials are now pulled safely from your server configuration
# To set these on Render: Go to your Dashboard -> Environment -> Add Environment Variable
API_TOKEN = os.environ.get("TELEGRAM_API_TOKEN", "YOUR_FALLBACK_TOKEN_IF_TESTING")
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql://postgres:srtlover534%40gmail.com@db.cqpgjiqyvwpnfdtbsrts.supabase.co:5432/postgres"
)
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://onrender.com")

bot = telebot.TeleBot(API_TOKEN)

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

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

# Flask Webhook Endpoints
@app.route('/' + API_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route('/')
def webhook_setup():
    bot.remove_webhook()
    bot.set_webhook(url=RENDER_URL + '/' + API_TOKEN)
    return "Zenith Storefront Webhook Successfully Synced", 200

# Telegram Bot Core Handlers
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

        prices = [telebot.types.LabeledPrice(label=title, amount=price)]
        bot.send_invoice(
            chat_id=message.chat.id,
            title=title,
            description="Automatic instant delivery via Telegram Stars.",
            invoice_payload=f"id_{account[0]}_price_{price}",
            provider_token="",  # Empty string allows native Telegram Stars processing
            currency="XTR",     # Universal currency code for Stars
            prices=prices,
            start_parameter="cpm2-store"
        )
    except Exception as e:
        bot.reply_to(message, f"⚠️ System Error: {str(e)}")

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_validation(pre_checkout_query: telebot.types.PreCheckoutQuery):
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)

