import sys
import types
if 'imghdr' not in sys.modules:
    sys.modules['imghdr'] = types.ModuleType('imghdr')

import os
import json
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask
from thefuzz import process, fuzz
from deep_translator import GoogleTranslator  # <--- Neu!

app = Flask(__name__)
@app.route('/')
def health_check(): return "OK", 200
def run_flask(): app.run(host='0.0.0.0', port=10000)

user_languages = {}

def load_knowledge():
    try:
        with open('wissen.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

# Neue Übersetzungs-Funktion
async def translate_text(text, target_lang):
    if target_lang == 'en':
        try:
            # Übersetzt von Deutsch nach Englisch
            return GoogleTranslator(source='de', target='en').translate(text)
        except:
            return text
    return text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"),
                InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]]
    await update.message.reply_text("Bitte Sprache wählen / Choose language:", 
                                   reply_markup=InlineKeyboardMarkup(buttons))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data.startswith("lang_"):
        lang = query.data.split("_")[1]
        user_languages[user_id] = lang
        knowledge = load_knowledge()
        buttons = []
        for kat in knowledge.keys():
            txt = await translate_text(kat.capitalize(), lang)
            buttons.append([InlineKeyboardButton(txt, callback_data=f"cat_{kat}")])
        welcome = "Wie kann ich helfen?" if lang == 'de' else "How can I help you?"
        await query.edit_message_text(welcome, reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data.startswith("cat_"):
        lang = user_languages.get(user_id, "de")
        cat = query.data.split("_")[1]
        knowledge = load_knowledge()
        kat_data = knowledge.get(cat, {})
        buttons = []
        for frage in kat_data.get("fragen", {}).keys():
            txt = await translate_text(frage, lang)
            buttons.append([InlineKeyboardButton(txt, callback_data=f"ans_{cat}_{frage[:15]}")] )
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"lang_{lang}")])
        await query.edit_message_text("Fragen:", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    lang = user_languages.get(user_id, "de")
    user_text = update.message.text
    knowledge = load_knowledge()
    
    all_data = {}
    for kat_val in knowledge.values():
        for f, a in kat_val.get("fragen", {}).items():
            all_data[f] = a
            
    search_query = user_text
    if lang == 'en':
        try: search_query = translator.translate(user_text, src='en', dest='de').text
        except: pass

    best_match, score = process.extractOne(search_query, all_data.keys(), scorer=fuzz.token_set_ratio)
    
    if score > 65:
        antwort = all_data[best_match]
        final_msg = await translate_text(antwort, lang)
        await update.message.reply_text(final_msg)
    else:
        fail = "Das habe ich leider nicht verstanden." if lang == 'de' else "I didn't understand that."
        await update.message.reply_text(fail)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        app_bot = Application.builder().token(token).build()
        app_bot.add_handler(CommandHandler("start", start))
        app_bot.add_handler(CallbackQueryHandler(handle_callback))
        app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        print("Bot startet erfolgreich...")
        app_bot.run_polling()
