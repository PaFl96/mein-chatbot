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
from deep_translator import GoogleTranslator
from langdetect import detect

# Flask Setup für Render
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

def translate_text(text, target_lang):
    if target_lang == 'en':
        try:
            return GoogleTranslator(source='de', target='en').translate(text)
        except:
            return text
    return text

async def show_main_menu(update, lang):
    """Erzeugt das Kachel-Menü (2 Spalten)"""
    knowledge = load_knowledge()
    buttons = []
    row = []
    
    for key, data in knowledge.items():
        titel = data.get("titel", key.capitalize())
        display_text = translate_text(titel, lang)
        row.append(InlineKeyboardButton(display_text, callback_data=f"cat_{key}"))
        
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row: buttons.append(row)

    text = "Wähle einen Bereich:" if lang == 'de' else "Please choose a section:"
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"),
                InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]]
    await update.message.reply_text("Sprache wählen / Choose language:", 
                                   reply_markup=InlineKeyboardMarkup(buttons))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    knowledge = load_knowledge()
    
    if query.data.startswith("lang_"):
        lang = query.data.split("_")[1]
        user_languages[user_id] = lang
        await show_main_menu(update, lang)

    elif query.data.startswith("cat_"):
        lang = user_languages.get(user_id, "de")
        cat = query.data.split("_")[1]
        kat_data = knowledge.get(cat, {})
        buttons = []
        for frage in kat_data.get("fragen", {}).keys():
            btn_txt = translate_text(frage, lang)
            buttons.append([InlineKeyboardButton(btn_txt, callback_data=f"ans_{cat}_{frage[:20]}")])
        
        back_txt = "🔙 Zurück" if lang == 'de' else "🔙 Back"
        buttons.append([InlineKeyboardButton(back_txt, callback_data="main_menu")])
        await query.edit_message_text("Fragen:", reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data == "main_menu":
        lang = user_languages.get(user_id, "de")
        await show_main_menu(update, lang)

    elif query.data.startswith("ans_"):
        lang = user_languages.get(user_id, "de")
        _, cat, short_frage = query.data.split("_", 2)
        kat_data = knowledge.get(cat, {})
        for frage, antwort in kat_data.get("fragen", {}).items():
            if frage.startswith(short_frage):
                final_msg = translate_text(antwort, lang)
                buttons = [[InlineKeyboardButton("🔙 Zurück", callback_data=f"cat_{cat}")]]
                await query.edit_message_text(final_msg, reply_markup=InlineKeyboardMarkup(buttons))
                break

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text
    knowledge = load_knowledge()
    
    if user_id not in user_languages:
        try:
            det = detect(user_text)
            user_languages[user_id] = 'en' if det == 'en' else 'de'
        except: user_languages[user_id] = 'de'

    lang = user_languages.get(user_id, "de")
    all_questions = {f: a for cat in knowledge.values() for f, a in cat.get("fragen", {}).items()}
    
    search_query = user_text
    if lang == 'en':
        try: search_query = GoogleTranslator(source='en', target='de').translate(user_text)
        except: pass

    best_match, score = process.extractOne(search_query, all_questions.keys(), scorer=fuzz.token_set_ratio)
    
    if score > 65:
        antwort = all_questions[best_match]
        await update.message.reply_text(translate_text(antwort, lang))
    else:
        await update.message.reply_text("Nicht verstanden." if lang == 'de' else "I didn't understand.")

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        app_bot = Application.builder().token(token).build()
        app_bot.add_handler(CommandHandler("start", start))
        app_bot.add_handler(CallbackQueryHandler(handle_callback))
        app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app_bot.run_polling()
