import os
import json
import requests
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    Updater,
    CommandHandler,
    InlineQueryHandler,
    CallbackContext,
    MessageHandler,
    Filters
)
import sseclient
from io import BytesIO

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN') or '7248206037:AAGH8liGlIksZE6rY7-mGI44qoVh1sOI4Gs'
BETTER_COPE_API = 'https://bettercopelk.navinda.xyz/api'

# Initialize bot
updater = Updater(TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Helper function to handle SSE stream
def get_subtitles_sse(query):
    url = f"{BETTER_COPE_API}/search?query={query}"
    response = requests.get(url, stream=True)
    client = sseclient.SSEClient(response)
    subtitles = []
    for event in client.events():
        if event.data:
            data = json.loads(event.data)
            subtitles.append(data)
    return subtitles

# Start command handler
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Welcome to BetterCopelk Subtitle Bot!\n\n"
        "You can:\n"
        "1. Search subtitles via inline mode (type @YourBotName in any chat)\n"
        "2. Send me a movie name to search\n"
        "3. Bulk download by sending multiple subtitle links"
    )

# Inline query handler
def inline_query(update: Update, context: CallbackContext):
    query = update.inline_query.query
    if not query:
        return
    
    results = []
    subtitles = get_subtitles_sse(query)
    
    for idx, sub in enumerate(subtitles[:50]):  # Telegram limits to 50 results
        title = f"{sub.get('title', 'No title')} ({sub.get('language', 'Unknown')})"
        description = f"Source: {sub.get('source', 'Unknown')}"
        
        results.append(
            InlineQueryResultArticle(
                id=str(idx),
                title=title,
                description=description,
                input_message_content=InputTextMessageContent(
                    f"Subtitle: {title}\n"
                    f"Download: /download_{sub['source']}_{sub['postUrl'].split('/')[-1]}"
                ),
                thumb_url=sub.get('thumbnail')
            )
        )
    
    update.inline_query.answer(results)

# Download handler
def download_subtitle(update: Update, context: CallbackContext):
    message_text = update.message.text
    
    if message_text.startswith('/download_'):
        # Handle individual download
        parts = message_text.split('_')
        source = parts[1]
        post_url = f"https://bettercopelk.navinda.xyz/api/download?postUrl={'/'.join(parts[2:])}&source={source}"
        
        try:
            response = requests.get(post_url)
            if response.status_code == 200:
                update.message.reply_document(
                    document=BytesIO(response.content),
                    filename=f'subtitle_{source}.zip'
                )
            else:
                update.message.reply_text("Failed to download subtitle")
        except Exception as e:
            update.message.reply_text(f"Error: {str(e)}")
    
    elif message_text.startswith('http'):
        # Handle bulk download
        urls = [u for u in message_text.split() if u.startswith('http')]
        data = {"data": []}
        
        for url in urls:
            if 'bettercopelk.navinda.xyz' in url:
                params = dict(p.split('=') for p in url.split('?')[1].split('&'))
                data["data"].append({
                    "postUrl": params.get('postUrl', ''),
                    "source": params.get('source', '')
                })
        
        if data["data"]:
            try:
                response = requests.post(
                    f"{BETTER_COPE_API}/bulk-download",
                    json=data
                )
                if response.status_code == 200:
                    update.message.reply_document(
                        document=BytesIO(response.content),
                        filename='bulk_subtitles.zip'
                    )
                else:
                    update.message.reply_text("Failed to download bulk subtitles")
            except Exception as e:
                update.message.reply_text(f"Error: {str(e)}")

# Message handler for regular search
def search_subtitles(update: Update, context: CallbackContext):
    query = update.message.text
    if query.startswith('/'):
        return
    
    subtitles = get_subtitles_sse(query)
    
    if not subtitles:
        update.message.reply_text("No subtitles found for your query.")
        return
    
    response = "Search Results:\n\n"
    for sub in subtitles[:10]:  # Show first 10 results
        response += (
            f"🎬 {sub.get('title', 'No title')}\n"
            f"🌐 Language: {sub.get('language', 'Unknown')}\n"
            f"📌 Source: {sub.get('source', 'Unknown')}\n"
            f"⬇️ Download: /download_{sub['source']}_{sub['postUrl'].split('/')[-1]}\n\n"
        )
    
    update.message.reply_text(response)

# Set up handlers
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(InlineQueryHandler(inline_query))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, search_subtitles))
dispatcher.add_handler(MessageHandler(Filters.regex(r'^(/download_|http)'), download_subtitle))

# Start the bot
updater.start_polling()
updater.idle()
