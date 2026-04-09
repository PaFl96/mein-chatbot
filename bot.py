import os
import json
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask
import threading

# Flask für den Render Health Check (damit der Bot online bleibt)
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is alive", 200

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# --- GOOGLE SHEETS LOGIK ---

def load_knowledge_from_sheet():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        # Holt den JSON-Schlüssel aus den Render-Umgebungsvariablen
        service_account_info = json.loads(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"))
        creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        client = gspread.authorize(creds)
        
        # HIER DEN NAMEN DEINES SHEETS ANPASSEN
        sheet = client.open("Bot_Wissensdatenbank").worksheet("FAQ")
        
        records = sheet.get_all_records()
        knowledge = {}
        
        for row in records:
            key = str(row['Schlüsselwort']).lower().strip()
            content_raw = row['Inhalt (JSON)']
            try:
                knowledge[key] = json.loads(content_raw)
            except:
                continue
        return knowledge
    except Exception as e:
        print(f"Fehler beim Laden des Sheets: {e}")
        return {}

# --- BOT LOGIK ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Wir laden das Wissen bei jedem /start frisch aus dem Sheet
    knowledge = load_knowledge_from_sheet()
    first_page = knowledge.get("start") # Du solltest eine Zeile "start" im Sheet haben
    
    if first_page:
        text = first_page["text"]
        buttons = [[InlineKeyboardButton(b[0], callback_data=b[1])] for b in first_page["buttons"]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text("Willkommen! Tippe ein Thema ein oder nutze das Menü.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    knowledge = load_knowledge_from_sheet()
    data = knowledge.get(query.data)
    
    if data:
        text = data["text"]
        buttons = [[InlineKeyboardButton(b[0], callback_data=b[1])] for b in data["buttons"]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(text, reply_markup=reply_markup)

def main():
    # Flask in einem eigenen Thread starten
    threading.Thread(target=run_flask, daemon=True).start()

    # Bot starten
    token = os.environ.get("TELEGRAM_TOKEN")
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling()

if __name__ == '__main__':
    main()
