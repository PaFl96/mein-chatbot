from langdetect import detect
import sys
import types

# Fix für fehlende Module in neuen Python-Versionen
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

# Flask für Render Health Check
app = Flask(__name__)
@app.route('/')
def health_check(): return "OK", 200
def run_flask(): app.run(host='0.0.0.0', port=10000)

user_languages = {}

def load_knowledge():
    """Lädt die lokale wissen.json Datei"""
    try:
        with open('wissen.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Fehler beim Laden der wissen.json: {e}")
        return {}

def translate_text(text, target_lang):
    """Übersetzt Text live ins Englische, wenn nötig"""
    if target_lang == 'en':
        try:
            return GoogleTranslator(source='de', target='en').translate(text)
        except Exception as e:
            print(f"Übersetzungsfehler: {e}")
            return text
    return text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Startet den Bot und zeigt die Sprachwahl"""
    buttons = [[InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"),
                InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]]
    await update.message.reply_text("Willkommen! Bitte wähle eine Sprache:\nWelcome! Please choose a language:", 
                                   reply_markup=InlineKeyboardMarkup(buttons))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verarbeitet Button-Klicks"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    knowledge = load_knowledge()
    
    if query.data.startswith("lang_"):
        lang = query.data.split("_")[1]
        user_languages[user_id] = lang
        
        buttons = []
        for kat in knowledge.keys():
            txt = translate_text(kat.capitalize(), lang)
            buttons.append([InlineKeyboardButton(txt, callback_data=f"cat_{kat}")])
        
        text = "Wobei kann ich helfen?" if lang == 'de' else "How can I help you?"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data.startswith("cat_"):
        lang = user_languages.get(user_id, "de")
        cat = query.data.split("_")[1]
        kat_data = knowledge.get(cat, {})
        
        buttons = []
        for frage in kat_data.get("fragen", {}).keys():
            btn_txt = translate_text(frage, lang)
            buttons.append([InlineKeyboardButton(btn_txt, callback_data=f"ans_{cat}_{frage[:20]}")] )
        
        back_txt = "🔙 Zurück" if lang == 'de' else "🔙 Back"
        buttons.append([InlineKeyboardButton(back_txt, callback_data=f"lang_{lang}")])
        
        text = "Hier sind die häufigsten Fragen:" if lang == 'de' else "Here are the most common questions:"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data.startswith("ans_"):
        lang = user_languages.get(user_id, "de")
        # Findet die Antwort im JSON basierend auf dem Callback
        _, cat, short_frage = query.data.split("_", 2)
        kat_data = knowledge.get(cat, {})
        for frage, antwort in kat_data.get("fragen", {}).items():
            if frage.startswith(short_frage):
                final_msg = translate_text(antwort, lang)
                back_txt = "🔙 Zurück" if lang == 'de' else "🔙 Back"
                buttons = [[InlineKeyboardButton(back_txt, callback_data=f"cat_{cat}")]]
                await query.edit_message_text(final_msg, reply_markup=InlineKeyboardMarkup(buttons))
                break

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text
    knowledge = load_knowledge()
    
    # Automatische Spracherkennung, falls keine Sprache im Speicher ist
    if user_id not in user_languages:
        try:
            detected_lang = detect(user_text)
            # Wenn Englisch erkannt wird, setze auf 'en', sonst 'de'
            user_languages[user_id] = 'en' if detected_lang == 'en' else 'de'
            print(f"Sprache für User {user_id} automatisch auf {user_languages[user_id]} gesetzt.")
        except:
            user_languages[user_id] = 'de' 

    lang = user_languages.get(user_id, "de")
    
    # Alle deutschen Fragen aus der wissen.json sammeln
    all_questions = {}
    for cat_val in knowledge.values():
        for f, a in cat_val.get("fragen", {}).items():
            all_questions[f] = a
            
    search_query = user_text
    # Falls die Sprache des Nutzers Englisch ist, übersetze die Frage für die Suche ins Deutsche
    if lang == 'en':
        try:
            search_query = GoogleTranslator(source='en', target='de').translate(user_text)
        except: 
            pass

    # Ähnlichkeitssuche mit thefuzz
    best_match, score = process.extractOne(search_query, all_questions.keys(), scorer=fuzz.token_set_ratio)
    
    if score > 65:
        antwort = all_questions[best_match]
        # Antwort bei Bedarf live ins Englische übersetzen
        final_msg = translate_text(antwort, lang)
        await update.message.reply_text(final_msg)
    else:
        # Fehlermeldung in der richtigen Sprache
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
        print("Bot bereit und wartet auf Nachrichten...")
        app_bot.run_polling()
