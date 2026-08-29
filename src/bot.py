import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from .dag import Dag
from .notifications import consume_pending_review, register_chat_id

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise RuntimeError('TELEGRAM_BOT_TOKEN not set in .env')

# Initialize DAG (shared state)
dag = Dag()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Welcome! Use /register, /add_node, /add_edge, /show, /visualize, or /export.')


async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat is None:
        return
    added = register_chat_id(chat.id)
    message = 'This chat is registered for human-review notifications.' if added else 'This chat is already registered for notifications.'
    await update.message.reply_text(message)


async def review_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if message is None or message.reply_to_message is None or not message.text:
        return
    review = consume_pending_review(message.chat_id, message.reply_to_message.message_id)
    if review is None:
        return
    node_id = review['node_id']
    try:
        status = dag.record_review_response(node_id, message.text, message.chat_id)
    except ValueError as error:
        await message.reply_text(f'Could not record this review: {error}')
        return
    await message.reply_text(f'Recorded your response for {node_id}. Status is now {status}.')


async def add_node(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        node_id = context.args[0]
        label = ' '.join(context.args[1:]) if len(context.args) > 1 else ''
        dag.add_node(node_id, label)
        await update.message.reply_text(f'Node {node_id} added.')
    except Exception as e:
        await update.message.reply_text(f'Error: {e}')


async def add_edge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        from_id, to_id = context.args[0], context.args[1]
        dag.add_edge(from_id, to_id)
        await update.message.reply_text(f'Edge {from_id}->{to_id} added.')
    except Exception as e:
        await update.message.reply_text(f'Error: {e}')


async def show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(str(dag))


async def visualize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from .visualize import generate_mermaid
    mermaid = generate_mermaid(dag)
    await update.message.reply_text(f'```mermaid\n{mermaid}\n```', parse_mode='MarkdownV2')


async def export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    export_path = os.getenv("DAG_EXPORT_FILE", str(Path(dag.state_file).with_name("dag_export.json")))
    with open(export_path, 'w') as f:
        json.dump(dag.to_dict(), f, indent=2)
    await update.message.reply_document(open(export_path, 'rb'))


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('register', register))
    app.add_handler(CommandHandler('add_node', add_node))
    app.add_handler(CommandHandler('add_edge', add_edge))
    app.add_handler(CommandHandler('show', show))
    app.add_handler(CommandHandler('visualize', visualize))
    app.add_handler(CommandHandler('export', export))
    app.add_handler(MessageHandler(filters.REPLY & filters.TEXT, review_reply))
    app.run_polling()


if __name__ == "__main__":
    main()
