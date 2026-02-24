import asyncio
import os
import requests
import base64
from datetime import datetime
from playwright.async_api import async_playwright
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, BroadcastRequest, ImageMessage
)

# --- 設定項目 ---
import os
LINE_TOKEN = os.environ.get('LINE_TOKEN')
IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY')

async def main():
    # 1. 今日の日付でファイル名を決定
    today_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"nikkei_heatmap_{today_str}.png"

    # 2. ヒートマップを撮影
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1280, "height": 720})
        
        print("TradingViewにアクセス中...")
        url = "https://jp.tradingview.com/heatmap/stock/#%7B%22dataSource%22%3A%22NI225%22%2C%22blockColor%22%3A%22change%22%2C%22blockSize%22%3A%22market_cap_basic%22%2C%22grouping%22%3A%22sector%22%7D"
        await page.goto(url, wait_until="load")
        await asyncio.sleep(15) # 切り替え待ち
        await page.screenshot(path=filename)
        await browser.close()
        print(f"画像保存完了: {filename}")

    # 3. 画像をImgBBにアップロードしてURLを取得
    print("画像をネット上にアップロード中...")
    with open(filename, "rb") as file:
        url = "https://api.imgbb.com/1/upload"
        payload = {
            "key": IMGBB_API_KEY,
            "image": base64.b64encode(file.read()),
        }
        res = requests.post(url, payload)
        image_url = res.json()["data"]["url"]
        print(f"画像URL取得成功: {image_url}")

    # 4. LINEで送信
    conf = Configuration(host="https://api.line.me")
    conf.access_token = LINE_TOKEN

    with ApiClient(conf) as api_client:
        line_bot_api = MessagingApi(api_client)
        # 画像メッセージを作成（originalとpreview両方にURLを入れる）
        image_message = ImageMessage(
            original_content_url=image_url,
            preview_image_url=image_url
        )
        request = BroadcastRequest(messages=[image_message])
        line_bot_api.broadcast(request)
        print("【成功】LINEにヒートマップを送信しました！")

if __name__ == "__main__":
    asyncio.run(main())