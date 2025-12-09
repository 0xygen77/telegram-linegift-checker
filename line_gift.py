import logging
import yaml
import asyncio
import httpx 
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load configuration
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

TOKEN = config["telegram"]["token"]
WEBHOOK_URL = config["telegram"]["webhook_url"]

user_requests = {}

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


async def fetch_and_check(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient() as client:
            logging.info(f"Fetching URL: {url}")
            response = await client.get(url, headers=headers, timeout=10.0)
            
            if response.status_code != 200:
                return f"Error: Status code {response.status_code}"

            soup = BeautifulSoup(response.text, "html.parser")
            
            try:
                button_box = soup.select_one(".button_bottom_box")
                if button_box:
                    content = button_box.get_text(strip=True)
                    logging.info(f"Fetched content: {content[:20]}...") # 只印前20字避免 log 太長
                    return content
                else:
                    return "Error: Cannot find button box"
            except Exception as e:
                return f"Parse Error: {e}"

    except Exception as e:
        logging.error(f"Error fetching URL {url}: {e}")
        return f"Network Error: {e}"

async def check_urls(context: ContextTypes.DEFAULT_TYPE):
    for user_id in list(user_requests.keys()):
        requests_list = user_requests[user_id]
        
        for item in list(requests_list):
            url, chat_id = item
            content = await fetch_and_check(url)

            if "Error" not in content:
                if content.find("Sold out 補貨中") == -1 and content.find("無法購買") == -1:
                    logging.info(f"Stock detected! URL: {url}")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"🚨 補貨通知！\n\n網址 {url} \n似乎已經可以購買了！"
                    )
                    user_requests[user_id].remove(item)

        if not user_requests[user_id]:
            del user_requests[user_id]


async def fetch_html_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        url = update.message.text.split(' ', 1)[1].strip()
    except IndexError:
        await update.message.reply_text("請輸入網址！例如: /add https://...")
        return

    if not url.startswith("https://giftshop-tw.line.me/voucher"):
        await update.message.reply_text("請輸入有效的 Line 禮物網址！")
        return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if user_id not in user_requests:
        user_requests[user_id] = []

    if any(url == req[0] for req in user_requests[user_id]):
        await update.message.reply_text("這網址已經在監控清單中了。")
        return

    user_requests[user_id].append((url, chat_id))
    logging.info(f"User {user_id} added URL: {url}")
    await update.message.reply_text(f"✅ 已新增監控：\n{url}")

async def del_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        url = update.message.text.split(' ', 1)[1].strip()
    except IndexError:
        await update.message.reply_text("請輸入要刪除的網址！")
        return

    user_id = update.effective_user.id
    
    if user_id not in user_requests:
        await update.message.reply_text("你沒有正在監控的網址。")
        return

    original_len = len(user_requests[user_id])
    user_requests[user_id] = [req for req in user_requests[user_id] if req[0] != url]
    
    if len(user_requests[user_id]) < original_len:
        await update.message.reply_text(f"🗑️ 已刪除網址：\n{url}")
    else:
        await update.message.reply_text("找不到這個網址。")

async def list_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_requests or not user_requests[user_id]:
        await update.message.reply_text("目前沒有監控中的網址。")
        return

    msg = "📋 目前監控清單：\n\n"
    for idx, (url, _) in enumerate(user_requests[user_id], 1):
        msg += f"{idx}. {url}\n"
    
    await update.message.reply_text(msg)

async def bot_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 **Bot 指令說明**\n\n"
        "/add <網址> - 新增監控網址\n"
        "/del <網址> - 刪除監控網址\n"
        "/list - 查看目前清單\n"
        "/start - 開始使用\n"
        "/help - 顯示此說明"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 歡迎！傳送 /help 查看如何使用。")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"收到訊息: {update.message.text}\n請使用 /add 加入網址。")

# --- 主程式區 ---

def main():
    # 建立 Application
    application = Application.builder().token(TOKEN).build()

    # 加入 Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", fetch_html_command))
    application.add_handler(CommandHandler("del", del_check))
    application.add_handler(CommandHandler("list", list_check))
    application.add_handler(CommandHandler("help", bot_help))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # 加入排程 Job (每 60 秒檢查一次)
    job_queue = application.job_queue
    job_queue.run_repeating(check_urls, interval=60, first=5)

    # 啟動 Webhook
    # 這裡會自動建立一個高效的 web server，不需要額外用 aiohttp
    logging.info(f"Starting Webhook on port 8443, path /{TOKEN}")
    
    application.run_webhook(
        listen="127.0.0.1",        # 只監聽本地，讓 Nginx 轉發
        port=8443,                 # 指定 Port
        url_path=TOKEN,            # 設定路徑為 Token (配合 Nginx)
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}" # 告訴 Telegram 完整的 Webhook 網址
    )

if __name__ == "__main__":
    main()
