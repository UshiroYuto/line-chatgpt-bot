import os
import logging

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import (
    InvalidSignatureError,
    LineBotApiError
)
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
from openai.error import RateLimitError

# ログ出力を INFO レベルで
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# 環境変数から読み込み
LINE_CHANNEL_SECRET      = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN= os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
OPENAI_API_KEY           = os.getenv("OPENAI_API_KEY", "")
# ここでモデル名を定義
MODEL_NAME               = "gpt-4o"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler      = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

# キャラクター設定
PERSONA_PROMPT = """
あなたは「不条理コントユニットMELT」の全てを知り尽くしている秘書、
トマソン君です。以下の特徴で応答してください。
- MELTの歴史やメンバー構成、過去の公演内容を詳細に理解している
- いつもフレンドリーかつきさくで、メンバーの相談にも気さくに乗る
- 必要な情報を即座に提供し、次のアクションを提案する
- 敬語とタメ口を使い分け、相談者がリラックスできる口調
"""

# グループ／ルームでのメンション検知用
BOT_NAME = "＠トマソン君"  # 全角か半角かログを見て合わせてください

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text

    # グループ／ルーム時はメンション必須
    if event.source.type in ("group", "room"):
        if BOT_NAME not in text:
            return
        text = text.replace(BOT_NAME, "").strip()

    # system + user メッセージを組み立て
    messages = [
        {"role": "system", "content": PERSONA_PROMPT},
        {"role": "user",   "content": text}
    ]

    # モデル名をログに出力
    logging.info(f"⏩ calling OpenAI with model={MODEL_NAME}")

    try:
        resp = openai.ChatCompletion.create(
            model=MODEL_NAME,
            messages=messages
        )
        reply = resp.choices[0].message.content.strip()
    except RateLimitError:
        reply = "申し訳ありません。現在混み合っていて応答できません。"

    # グループなら push_message、1:1なら reply_message
    try:
        if event.source.type == "group":
            line_bot_api.push_message(
                event.source.group_id,
                TextSendMessage(text=reply)
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply)
            )
    except LineBotApiError as e:
        logging.error(f"LineBotApiError: {e}")

if __name__ == "__main__":
    app.run()
