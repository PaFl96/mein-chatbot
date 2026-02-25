import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from thefuzz import fuzz
from deep_translator import GoogleTranslator

# --- DIESER TEIL IST FÜR RENDER (FREE TIER) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")

def run_health_check():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()
# ----------------------------------------------

import os
APP_TOKEN = os.environ.get("TELEGRAM_TOKEN")

def translate_text(text, target_lang='de'):
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except Exception:
        return text

def load_knowledge():
    if os.path.exists('wissen.json'):
        try:
            with open('wissen.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    knowledge = load_knowledge()
    user_text = update.message.text
    text_internal = translate_text(user_text, target_lang='de').lower()
    
    found_key = None
    for key in knowledge.keys():
        if fuzz.partial_ratio(key.lower(), text_internal) > 75:
            found_key = key
            break
            
    if found_key:
        fragen = knowledge[found_key]["fragen"]
        buttons = [[InlineKeyboardButton(translate_text(q, target_lang='en') if user_text.lower() != text_internal else q, callback_data=q)] for q in fragen.keys()]
        msg = "I found something:" if user_text.lower() != text_internal else "Ich habe etwas gefunden:"
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        no_match = "Dazu habe ich leider keine Infos."
        reply = translate_text(no_match, target_lang='en') if user_text.lower() != text_internal else no_match
        await update.message.reply_text(reply)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    knowledge = load_knowledge()
    query = update.callback_query
    await query.answer()
    selected_q = query.data
    user_lang_is_en = "found" in query.message.text.lower()
    
    answer = "Keine Antwort gefunden."
    for cat in knowledge.values():
        if selected_q in cat["fragen"]:
            answer = cat["fragen"][selected_q]
            break
    
    final_answer = translate_text(answer, target_lang='en') if user_lang_is_en else answer
    await query.edit_message_text(text=f"Answer: {final_answer}" if user_lang_is_en else f"Antwort: {answer}")

if __name__ == '__main__':
    # Startet den Herzschlag-Server für Render in einem eigenen Thread
    threading.Thread(target=run_health_check, daemon=True).start()
    
    app = ApplicationBuilder().token(APP_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    app.add_handler(CallbackQueryHandler(handle_buttons))

    app.run_polling()

