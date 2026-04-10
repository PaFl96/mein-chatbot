import os
import json
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask
from thefuzz import process, fuzz
from googletrans import Translator

# Flask für Render
app = Flask(__name__)
@app.route('/')
def health_check(): return "OK", 200
def run_flask(): app.run(host='0.0.0.0', port=10000)

translator = Translator()
user_languages = {}

def load_knowledge():
    with open('wissen.json', 'r', encoding='utf-8') as f:
        return json.load(f)

async def translate_if_needed(text, target_lang):
    if target_lang == 'en':
        try:
            translated = translator.translate(text, src='de', dest='en')
            return translated.text
        except:
            return text # Fallback auf Deutsch bei Fehler
    return text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"),
                InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]]
    await update.message.reply_text("Bitte wähle eine Sprache / Choose a language:", 
                                   reply_markup=InlineKeyboardMarkup(buttons))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    lang = query.data.split("_")[1]
    user_languages[user_id] = lang
    
    knowledge = load_knowledge()
    buttons = []
    
    # Menü-Buttons übersetzen, falls Englisch gewählt
    for kat in knowledge.keys():
        btn_text = await translate_if_needed(kat.capitalize(), lang)
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"cat_{kat}")])
    
    welcome_text = "Wie kann ich helfen?" if lang == 'de' else "How can I help you?"
    await query.edit_message_text(welcome_text, reply_markup=InlineKeyboardMarkup(buttons))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    lang = user_languages.get(user_id, "de")
    user_text = update.message.text
    knowledge = load_knowledge()
    
    # Alle Fragen aus dem deutschen JSON sammeln
    all_questions = {}
    for cat in knowledge.values():
        for frage, antwort in cat["fragen"].items():
            all_questions[frage] = antwort
            
    # Suche mit thefuzz (auf Deutsch, da JSON deutsch ist)
    # Falls User Englisch schreibt, übersetzen wir die Frage kurz intern auf Deutsch für die Suche
    search_query = user_text
    if lang == 'en':
        try: search_query = translator.translate(user_text, src='en', dest='de').text
        except: pass

    best_match, score = process.extractOne(search_query, all_questions.keys(), scorer=fuzz.token_set_ratio)
    
    if score > 60:
        antwort = all_questions[best_match]
        final_text = await translate_if_needed(antwort, lang)
        await update.message.reply_text(final_text)
    else:
        fail_msg = "Das habe ich nicht verstanden." if lang == 'de' else "I didn't understand that."
        await update.message.reply_text(fail_msg)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    token = os.environ.get("TELEGRAM_TOKEN")
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()
