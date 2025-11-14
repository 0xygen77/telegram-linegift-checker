import logging
import requests
import yaml
import asyncio
from bs4 import BeautifulSoup
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load configuration from config.yaml
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

TOKEN = config["telegram"]["token"]
WEBHOOK_URL = config["telegram"]["webhook_url"]

user_requests = {}

# Enable logging
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# Async Telegram Bot Application
application = Application.builder().token(TOKEN).build()

async def fetch_html(update: Update, context):
    url = update.message.text.split(' ', 1)[1]

    if not url.startswith("https://giftshop-tw.line.me/voucher"):
        await update.message.reply_text("請輸入有效的 Line 禮物網址！(e.g., <code>https://giftshop-tw.line.me/voucher/123456</code>)", parse_mode="html")
        return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    logging.info(f"User {user_id} added URL: {url}")

    if user_id not in user_requests:
        user_requests[user_id] = []

    user_requests[user_id].append((url, chat_id))
    await update.message.reply_text(f"已新增網址至監控清單：{url}")

async def del_check(update: Update, context):
    url = update.message.text.split(' ', 1)[1]
    
    if not url.startswith("https://giftshop-tw.line.me/voucher"):
        await update.message.reply_text("請輸入有效的 Line 禮物網址！(e.g., <code>https://giftshop-tw.line.me/voucher/123456</code>)", parse_mode="html")
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    logging.info(f"User {user_id} deleted URL: {url}")

    if user_id not in user_requests:
        await update.message.reply_text(f"查無紀錄。")
        return

    user_requests[user_id].remove((url, chat_id))
    await update.message.reply_text(f"已刪除網址：{url}")

async def list_check(update: Update, context):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    logging.info(f"User {user_id} shows his list.")

    if user_id not in user_requests:
        await update.message.reply_text("查無紀錄。")
        return

    user_list = ""
    for i in user_requests[user_id]:
        user_list += i[0] + '\n'

    await update.message.reply_text(user_list)

async def bot_help(update: Update, context):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    logging.info(f"User {user_id} shows help.")

    await update.message.reply_text(
            f"輸入 /add <網址> 新增網址。\n"
            f"輸入 /list 查詢目前監測的網址。\n"
            f"輸入 /del <網址> 刪除該網址的監測。\n"
            f"輸入 /help 回答這些訊息。"
        )

def fetch_and_check(url):
    try:
        logging.info(f"Fetching URL: {url}")
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        button_box_content = soup.select_one(".button_bottom_box").get_text(strip=True)
        logging.info(f"Fetched content from {url}: {button_box_content}")
        return button_box_content
    except Exception as e:
        logging.error(f"Error fetching URL {url}: {e}")
        return f"Error: {e}"

async def check_urls(context: ContextTypes.DEFAULT_TYPE):
    """定期檢查所有使用者的 URL"""
    for user_id, requests_list in list(user_requests.items()):
        for url, chat_id in requests_list:
            content = fetch_and_check(url)

            if content.find("Sold out 補貨中") == -1 and content.find("無法購買") == -1:
                logging.info(f"Content change detected for URL {url}, notifying user {user_id}.")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"網址 {url} 已補貨！！"
                )
                user_requests[user_id].remove((url, chat_id))

        if not user_requests[user_id]:
            logging.info(f"All URLs processed for user {user_id}, removing from tracking.")
            del user_requests[user_id]

async def start(update: Update, context):
    logging.info("Received /start command from user: %s", update.message.from_user.id)
    await update.message.reply_text("此 bot 能接收 Line 禮物網址並每分鐘檢查是否有補貨，如果有補貨會通知你。")

async def echo(update: Update, context):
    await update.message.reply_text(f"You said: {update.message.text}")

# Add handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("add", fetch_html))
application.add_handler(CommandHandler("del", del_check))
application.add_handler(CommandHandler("list", list_check))
application.add_handler(CommandHandler("help", bot_help))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

job_queue = application.job_queue
job_queue.run_repeating(check_urls, interval=60, first=0)


async def set_webhook():
    """Set the webhook for Telegram bot"""
    webhook_set = await application.bot.set_webhook(WEBHOOK_URL)
    if webhook_set:
        logging.info("Webhook set successfully!")

async def handle_webhook(request):
    """Handle incoming webhook requests"""
    update_data = await request.json()
    logging.info("Received update: %s", update_data)
    update = Update.de_json(update_data, application.bot)
    await application.update_queue.put(update)
    logging.info("Processed update.")
    return web.Response(text="OK")

async def run_aiohttp():
    """Run the aiohttp server"""
    app = web.Application()
    app.router.add_post("/webhook", handle_webhook)
    return app

async def main():
    """Initialize and run both Telegram bot and aiohttp server"""
    await set_webhook()
    await application.initialize()  # Ensure Application is initialized
    await application.start()       # Start the Telegram bot

    app = await run_aiohttp()       # Run the aiohttp server asynchronously
    logging.info("Starting aiohttp server...")
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 5000)
    await site.start()

    logging.info("Server started on https://127.0.0.1:5000")
    while True:
        await asyncio.sleep(3600)  # Keep the server running

if __name__ == "__main__":
    asyncio.run(main())
