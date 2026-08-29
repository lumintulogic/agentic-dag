import os
import logging
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
from .dag import Dag

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise RuntimeError('TELEGRAM_BOT_TOKEN not set in .env')

# Initialize DAG (shared state)
dag = Dag()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Welcome! Use /add_node, /add_edge, /show, /visualize, /export.')

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
    import json
    export_path = os.path.join(os.path.dirname(__file__), '..', 'dag_export.json')
    with open(export_path, 'w') as f:
        json.dump(dag.to_dict(), f, indent=2)
    await update.message.reply_document(open(export_path, 'rb'))

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('add_node', add_node))
    app.add_handler(CommandHandler('add_edge', add_edge))
    app.add_handler(CommandHandler('show', show))
    app.add_handler(CommandHandler('visualize', visualize))
    app.add_handler(CommandHandler('export', export))
    app.run_polling()

if __name__ == "__main__":
    main()
