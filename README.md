# Line Gift Monitor Bot (Line 禮物補貨通知機器人)

這是一個基於 Python 的 Telegram Bot，專門用於監測 **Line 禮物 (Line Gift)** 商品頁面。當使用者加入商品網址後，機器人會每分鐘自動檢查庫存狀態，一旦發現「補貨」或「可購買」，即會發送通知給該使用者。

本專案採用 **Webhook** 架構，配合 Nginx 反向代理與 Cloudflare SSL，並使用 `httpx` 非同步請求以確保高併發時的效能。

## ✨ 功能特色

* **非同步架構**：使用 `python-telegram-bot` (v20+) 與 `httpx`，檢查網頁時不會卡住 Bot 回應。
* **多使用者支援**：每個使用者擁有獨立的監控清單。
* **即時通知**：每 60 秒自動巡查，發現補貨立即推播。
* **Webhook 部署**：適合正式環境，比 Polling 更節省資源且反應更快。
* **指令管理**：支援 `/add`, `/del`, `/list` 等指令管理監控項目。

## 🛠️ 技術棧

* [Python 3.8+](https://www.python.org/)
* [python-telegram-bot](https://python-telegram-bot.org/) (Async framework)
* [httpx](https://www.python-httpx.org/) (Async HTTP client)
* [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) (HTML Parsing)
* Nginx (Reverse Proxy)

## 🚀 安裝與設定

### 1. 安裝依賴套件

建議使用虛擬環境 (venv)：

```bash
python3 -m venv venv
source venv/bin/activate
pip install python-telegram-bot httpx beautifulsoup4 pyyaml
````

### 2\. 設定 Config

請在專案根目錄建立 `config.yaml` 檔案，內容如下：

```yaml
telegram:
  token: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz" # 你的 Telegram Bot Token
  webhook_url: "[https://bot.yourdomain.com](https://bot.yourdomain.com)"     # 你的網域 (不需加 /TOKEN)
```

### 3\. 部署 (Nginx + Cloudflare)

本專案設計透過 Nginx 處理 SSL 並反向代理至 Bot。

**Cloudflare 設定：**

  * DNS A Record 指向伺服器 IP (開啟 Proxy/小橘雲)。
  * SSL/TLS 模式設為 **Full (Strict)**。
  * 建立 Origin Server Certificate 並存於伺服器。

**Nginx 設定 (`/etc/nginx/sites-available/telegram-bot`)：**

```nginx
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name bot.yourdomain.com;

    # Cloudflare Origin CA 憑證
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        # 轉發給 Python Bot (監聽 8443)
        proxy_pass [http://127.0.0.1:8443](http://127.0.0.1:8443);
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 4\. 啟動機器人

直接執行 Python 腳本：

```bash
python3 main.py
```

## 🤖 使用指令

| 指令 | 說明 | 範例 |
| :--- | :--- | :--- |
| `/start` | 啟用機器人 | `/start` |
| `/add <url>` | 新增監控網址 | `/add https://giftshop-tw.line.me/...` |
| `/del <url>` | 刪除監控網址 | `/del https://giftshop-tw.line.me/...` |
| `/list` | 列出目前監控清單 | `/list` |
| `/help` | 顯示說明 | `/help` |

## ⚠️ 免責聲明

本工具僅供個人學習與技術研究使用。請勿用於惡意頻繁請求導致目標網站負擔。使用爬蟲技術可能違反部分網站的使用條款，請使用者自行承擔風險。

