import logging
from dotenv import load_dotenv
import os

import requests
from asgiref.sync import sync_to_async
from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, \
    CallbackQueryHandler, filters
from telegram.helpers import escape_markdown

from database import Database
from user_package.wrapper_functions import *

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Definisci gli stati della conversazione
TRACK, VALIDATE_LINK = range(2)


# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    effective_user = update.effective_user
    await sync_to_async(get_db_user_by_telegram_effective_user)(effective_user)
    await update.message.reply_markdown_v2(
        'Ciao\! Benvenuto in *PyPi Package Updates Bot*\n\n'
        'Posso tenere sotto controllo i packages da PyPi e segnalarti aggiornamenti '
        'di versione con il changelog completo\.\n\n'
        'Per iniziare inviami subito il comando /track\n\n'
        '>Bot repo: [github\.com](https://github.com/progressify/pypi_package_updates_bot)\n'
        '>Author: [progressify\.dev](https://progressify.dev)\n',
        disable_web_page_preview=True
    )


# Comando /track per iniziare la conversazione
async def track(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_markdown_v2(
        'Inviami il link PyPi del package che vuoi tracciare',
        reply_markup=ForceReply(selective=True)
    )
    return VALIDATE_LINK


# Validazione del link
async def validate_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    effective_user = update.effective_user
    link = update.message.text

    user = await sync_to_async(get_db_user_by_telegram_effective_user)(effective_user)

    is_valid = False
    if link.startswith('https://pypi.org/'):
        is_valid = True

    slug = ''
    actual_version = ''
    if is_valid:
        if link.endswith('/'):
            link = link[:-1]

        splitted_link = link.split('/')
        splitted_len = len(splitted_link)
        counter = splitted_len - 1
        while len(splitted_link[counter]) == 0 or '#' in splitted_link[counter]:
            counter -= 1

        slug = splitted_link[counter]
        response = requests.get(f"https://pypi.org/pypi/{slug}/json")
        if response.status_code == 200:
            is_valid = True
            actual_version = response.json()['info']['version']
        else:
            is_valid = False

    if is_valid:
        # controlla se l'utente sta già tracciando quella stessa libreria
        user_packages = await sync_to_async(get_user_packages_slug_list)(user)
        if slug in user_packages:
            await update.message.reply_markdown_v2(
                f'❗️Stai già tracciando `{slug}`\n'
                'Quando verrà pubblicata una nuova release, sarai il primo a essere avvisato :\)'
            )
            return ConversationHandler.END

        await sync_to_async(create_user_package)(
            user,
            {
                'link': link,
                'slug': slug,
                'last_check_version': actual_version
            }
        )
        actual_version = escape_markdown(actual_version, version=2)
        await update.message.reply_markdown_v2(
            '✅ Package memorizzato\!\n\n'
            f'`{slug}` attualmente è alla versione `{actual_version}`\n'
            'Ti invierò una notifica quando verrà rilasciata una nuova versione',
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            '❌ Il link non è valido.\n'
            'Posso tracciare solo le librerie disponibili su https://pypi.org'
        )
        return ConversationHandler.END


# Comando /cancel per interrompere la conversazione
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Operazione annullata')
    return ConversationHandler.END


# Comando /list per visualizzare i link memorizzati
async def list_links(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    effective_user = update.effective_user

    user = await sync_to_async(get_db_user_by_telegram_effective_user)(effective_user)
    links = await sync_to_async(get_user_packages_slug_list)(user)

    if len(links) == 0:
        await update.message.reply_markdown_v2(
            'Non stai tracciando nessuna libreria\.\n'
            'Inizia subito tramite il comando /track'
        )
        return

    keyboard = [[InlineKeyboardButton(link, callback_data=link)] for link in links]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await update.message.reply_text('Ecco le librerie che stai tracciando:', reply_markup=reply_markup)
    except Exception as e:
        await update.callback_query.edit_message_text(
            'Ecco le librerie che stai tracciando:',
            reply_markup=reply_markup
        )


# Callback per la pulsantiera
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    effective_user = update.effective_user

    user = await sync_to_async(get_db_user_by_telegram_effective_user)(effective_user)

    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "list":
        await list_links(update, context)
    elif data.startswith("unfollow:"):
        slug = query.data.split(":", 1)[1]
        await sync_to_async(delete_user_package_by_slug)(user, slug)
        await query.edit_message_text(text=f"Non stai più tracciando il package {data}")
    else:
        keyboard = [
            [InlineKeyboardButton("Smetti di seguire", callback_data=f"unfollow:{data}")],
            [InlineKeyboardButton("Torna alla lista", callback_data="list")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"Vuoi smettere di tracciare il package: {data}?",
            reply_markup=reply_markup
        )


async def scheduled_task(context: ContextTypes.DEFAULT_TYPE):
    packages = await sync_to_async(distinct_packages)()
    for package in packages:
        logger.info(f"Checking package {package.slug}")

        try:
            response = requests.get(f"https://pypi.org/pypi/{package.slug}/json")
        except Exception as e:
            logger.error(f"Error while checking package {package.slug}: {e}")
            continue

        if response.status_code != 200:
            logger.warning(f"Package {package.slug} not found")
            # todo meccanismo per scartare le librerie che danno errore
            return

        data = response.json()
        actual_version = data['info']['version']

        if package.last_check_version != actual_version:
            users = await sync_to_async(get_users_that_follow_package)(package.slug)
            for user in users:
                try:
                    escaped_actual_version = escape_markdown(actual_version, version=2)
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"✳️ Il package `{package.slug}` è stato aggiornato "
                             f"alla versione `{escaped_actual_version}`",
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                except Exception as e:
                    logger.error(f"Errore nell'invio del messaggio all'utente {user.telegram_id}: {e}")

            await sync_to_async(update_package_version)(package.slug, actual_version)


# Configura il bot
def main():
    db = Database(engine='django.db.backends.sqlite3', name='bot_persistence.db')
    from user_package.models import User, Package

    db.create_table(User)
    db.create_table(Package)

    db.update_table(User)
    db.update_table(Package)

    app = ApplicationBuilder().token(TOKEN).build()

    # Configura la job queue
    job_queue = app.job_queue
    # ogni 2 ore: 2 ore * 60 minuti * 60 secondi
    job_queue.run_repeating(scheduled_task, interval=7200, first=5, name="check_package_updates")

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('track', track)],
        states={
            VALIDATE_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, validate_link)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_links))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button, pattern=".*"))

    app.run_polling()


if __name__ == '__main__':
    main()
