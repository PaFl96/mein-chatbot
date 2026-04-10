import os
import json
import gspread
import threading
from google.oauth2.service_account import Credentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask

app = Flask(__name__)

@app.route('/')
def health_check(): return "OK", 200

def run_flask():
    app.run(host='0.0.0.0', port=10000)

def load_data():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        service_account_info = json.loads(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"))
        creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open("Bot_Wissensdatenbank").worksheet("FAQ")
        records = sheet.get_all_records()
        return {str(r['Schlüsselwort']).lower().strip(): json.loads(r['Inhalt (JSON)']) for r in records if r['Schlüsselwort']}
    except Exception as e:
        print(f"Fehler: {e}")
        return {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data().get("start")
    if data:
        buttons = [[InlineKeyboardButton(b[0], callback_data=b[1])] for b in data.get("buttons", [])]
        await update.message.reply_text(data["text"], reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text("Bitte 'start' im Google Sheet anlegen!")

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data().get(query.data)
    if data:
        buttons = [[InlineKeyboardButton(b[0], callback_data=b[1])] for b in data.get("buttons", [])]
        await query.edit_message_text(data["text"], reply_markup=InlineKeyboardMarkup(buttons))

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    token = os.environ.get("TELEGRAM_TOKEN")
    app_bot = Application.builder().token(token).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(handle_button))
    app_bot.run_polling()
