import os
import json
import gspread
import threading
from google.oauth2.service_account import Credentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask
from thefuzz import fuzz # Das Modul, das im Bild gefehlt hat

# Flask für Render Health Check
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
        # WICHTIG: Die Variable GOOGLE_SERVICE_ACCOUNT_JSON muss bei Render hinterlegt sein!
        service_account_info = json.loads(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"))
        creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        client = gspread.authorize(creds)
        
        # Name deines Sheets prüfen (Bot_Wissensdatenbank)
        sheet = client.open("Bot_Wissensdatenbank").worksheet("FAQ")
        
        records = sheet.get_all_records()
        knowledge = {}
        
        for row in records:
            # Wir nehmen 'Schlüsselwort' als Schlüssel
            key = str(row.get('Schlüsselwort', '')).lower().strip()
            if not key: continue
            
            content_raw = row.get('Inhalt (JSON)', '{}')
            try:
                knowledge[key] = json.loads(content_raw)
            except:
                print(f"Fehler beim Parsen von JSON für: {key}")
                continue
        return knowledge
    except Exception as e:
        print(f"Großer Fehler beim Laden des Sheets: {e}")
        return {}

# --- BOT LOGIK ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    knowledge = load_knowledge_from_sheet()
    # Der Bot sucht im Sheet nach einem Eintrag mit dem Schlüsselwort "start"
    data = knowledge.get("start")
    
    if data:
        text = data.get("text", "Willkommen!")
        buttons = []
        for b in data.get("buttons", []):
            buttons.append([InlineKeyboardButton(b[0], callback_data=b[1])])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text("Hallo! Bitte lege im Google Sheet einen Eintrag mit dem Schlüsselwort 'start' an.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    knowledge = load_knowledge_from_sheet()
    data = knowledge.get(query.data)
    
    if data:
        text = data.get("text", "Kein Text gefunden.")
        buttons = []
        for b in data.get("buttons", []):
            buttons.append([InlineKeyboardButton(b[0], callback_data=b[1])])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

def main():
    # Flask in Hintergrund starten
    threading.Thread(target=run_flask, daemon=True).start()

    token = os.environ.get("TELEGRAM_TOKEN")
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    print("Bot startet...")
    application.run_polling()

if __name__ == '__main__':
    main()
