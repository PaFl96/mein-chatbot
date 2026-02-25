import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from thefuzz import fuzz
from deep_translator import GoogleTranslator

# DEIN TOKEN HIER EINTRAGEN
APP_TOKEN = "8584441878:AAF9VFcb7Sb2XyM_Wz9GkB_GQDgc2nBqHro"

def translate_text(text, target_lang='de'):
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except Exception as e:
        print(f"Übersetzungsfehler: {e}")
        return text

def load_knowledge():
    """Lädt die Wissensdatenbank aus der JSON-Datei."""
    if os.path.exists('wissen.json'):
        try:
            with open('wissen.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except Exception as e:
            print(f"Fehler beim Lesen der JSON: {e}")
    return {}

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # AUTO-UPDATE: Lädt die Datei bei JEDER neuen Nachricht frisch ein
    knowledge = load_knowledge()
    
    user_text = update.message.text
    print(f"\nNutzer schreibt: {user_text}")
    
    # Intern alles auf Deutsch übersetzen und klein schreiben
    text_internal = translate_text(user_text, target_lang='de').lower()
    
    found_key = None
    # Wir suchen in den aktuell geladenen Daten
    for key in knowledge.keys():
        score = fuzz.partial_ratio(key.lower(), text_internal)
        if score > 75:
            found_key = key
            break
            
    if found_key:
        fragen = knowledge[found_key]["fragen"]
        buttons = []
        for q in fragen.keys():
            # Buttons für englische Nutzer übersetzen
            display_q = translate_text(q, target_lang='en') if user_text.lower() != text_internal else q
            buttons.append([InlineKeyboardButton(display_q, callback_data=q)])
        
        msg = "I found something:" if user_text.lower() != text_internal else "Ich habe etwas gefunden:"
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        no_match = "Dazu habe ich leider keine Infos."
        reply = translate_text(no_match, target_lang='en') if user_text.lower() != text_internal else no_match
        await update.message.reply_text(reply)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Auch hier laden wir die Daten neu, falls sich die Antwort gerade geändert hat
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
    
    if user_lang_is_en:
        final_answer = translate_text(answer, target_lang='en')
        await query.edit_message_text(text=f"Answer: {final_answer}")
    else:
        await query.edit_message_text(text=f"Antwort: {answer}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(APP_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    print("Bot mit Auto-Update aktiv... Warte auf Nachrichten.")
    app.run_polling()