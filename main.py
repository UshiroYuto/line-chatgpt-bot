import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
from openai.error import RateLimitError

app = Flask(__name__)

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

# グループ内でメンションがあったときだけ反応するためのBOT名
BOT_NAME = "@トマソン君"  # ここはBotの表示名に合わせてください

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # ユーザーからのテキストを取得
    text = event.message.text

    # グループ／ルームの場合は、メンションがなければ何もしない
    if event.source.type in ("group", "room"):
        if BOT_NAME not in text:
            return
        # メンション部分は除去
        text = text.replace(BOT_NAME, "").strip()

    # ChatGPTに投げて返信を得る
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": text}]
        )
        reply = resp.choices[0].message.content.strip()
    except RateLimitError:
        reply = "申し訳ありません。現在混み合っていて応答できません。"

    # LINEに返す
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

if __name__ == "__main__":
    app.run()
