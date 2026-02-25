import asyncio
import os
import requests
import base64
from datetime import datetime
from playwright.async_api import async_playwright

# 【重要】新しいライブラリの読み込み形式
from google import genai
from google.genai import types

from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, BroadcastRequest, ImageMessage, TextMessage
)

# --- 設定項目 ---
# 警告：APIキーやトークンを直接コードに書くとセキュリティリスクがあります。
# テストが終わったら、必ず環境変数から読み込む形 (os.environ.get) に戻すことを強くお勧めします。
LINE_TOKEN = os.environ.get('LINE_TOKEN')
IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# genai.configure ではなく、client という名前で初期化します
client = genai.Client(api_key=GEMINI_API_KEY)

async def main():
    # 1. 今日の日付でファイル名を決定
    today_str = datetime.now().strftime("%Y%m%d")
    filename = f"nikkei_heatmap_{today_str}.png"

    # 2. ヒートマップを高解像度で撮影
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # 高解像度化の設定: device_scale_factor=1 
        context = await browser.new_context(
            viewport={"width": 3440, "height": 1440},
            device_scale_factor=1
        )
        page = await context.new_page()
        
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
        upload_url = "https://api.imgbb.com/1/upload"
        payload = {
            "key": IMGBB_API_KEY,
            "image": base64.b64encode(file.read()),
        }
        res = requests.post(upload_url, payload)
        image_url = res.json()["data"]["url"]
        print(f"画像URL取得成功: {image_url}")

    # 4. Geminiで画像を分析
    print("AIによる画像分析中（Google検索を実行中）...")
    
    # 画像データの読み込み
    with open(filename, "rb") as f:
        image_bytes = f.read()

    # プロンプトの設定
    prompt = ( 

"＃あなたは日経新聞のプロの新聞記者です。次の内容を出力しなさい"
"＃形式"
"【｛今日の日付｝の日経225分析】"
"まず、市場の目立った動きや相場を100字程度でまとめる。"
"次に、株価変動の大きい注目すべき5銘柄（時価総額の大きさは問わない,なるべく異なるセクターから選ぶ）を画像から読み取る。その変動理由を120字程度で記述する。"
"出力形式は、銘柄名（ティッカー）,騰落率（符号を含めた数字のみ記載）：（改行して）変動理由"
"各銘柄説明の間は一行開ける。全体のメッセージの最後にhttps://moneyworld.jp/のリンクを添付する"
"＃条件"
"出力は常態（〜だ、〜である）で。「プロの視点から」などの冒頭の挨拶は不要。簡潔に回答して。"
"情報は全てその場で検索したものを載せること。株式会社QUICK（https://moneyworld.jp/）の記事が特に信頼できるので参照すること。"
"株式会社QUICK（https://moneyworld.jp/）に該当記事があるならそのリンクを実際に検索して、正しいURLを引用して。 "
    )

    # Geminiへのリクエスト送信
    response = client.models.generate_content(
        model="gemini-2.5-flash", # 利用可能な最新モデルに変更
        contents=[
            prompt,
            types.Part.from_bytes(data=image_bytes, mime_type="image/png")
        ],
        config=types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())]
        )
    )

    analysis_result = response.text
    print("分析完了")

    # 5. LINEで送信（画像 ＋ 分析結果のテキスト）
    conf = Configuration(host="https://api.line.me")
    conf.access_token = LINE_TOKEN

    with ApiClient(conf) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        # 画像メッセージ
        image_message = ImageMessage(
            original_content_url=image_url,
            preview_image_url=image_url
        )
        
        # AI分析テキストメッセージ
        text_message = TextMessage(
            text=f"【本日の日経225分析】\n\n{analysis_result}"
        )
        
        # 画像とテキストを同時に配信
        request = BroadcastRequest(messages=[image_message, text_message])
        line_bot_api.broadcast(request)
        print("【成功】LINEにヒートマップと分析結果を送信しました！")

if __name__ == "__main__":

    asyncio.run(main())
