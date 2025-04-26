import os
import logging
import traceback

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
from openai.error import RateLimitError

# ─── 設定セクション ───
logging.basicConfig(level=logging.INFO)

LINE_CHANNEL_SECRET       = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
OPENAI_API_KEY            = os.getenv("OPENAI_API_KEY", "")
MODEL_NAME                = "gpt-4o"   # ← ここでモデル変更
BOT_NAME                  = "＠トマソン君"  # 実際にログに出たメンション文字列に合わせて

PERSONA_PROMPT = """
あなたは「不条理コントユニットMELT」の全てを知り尽くしている秘書、
トマソン君です。以下の特徴で応答してください。
- MELTの歴史やメンバー構成、過去の公演内容を詳細に理解している
- いつもフレンドリーかつきさくで、メンバーの相談にも気さくに乗る
- 必要な情報を即座に提供し、次のアクションを提案する
- 敬語とタメ口を使い分け、相談者がリラックスできる口調
"""

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler      = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

# ─── Webhook入口 ───
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception:
        logging.error("Unhandled exception in callback:\n" + traceback.format_exc())
        abort(500)
    return "OK"

# ─── メッセージイベントハンドラ ───
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text
    logging.info(f"Received ({event.source.type}): {text}")

    # グループ／ルームではメンション必須
    if event.source.type in ("group", "room"):
        if BOT_NAME not in text:
            logging.info("→ BOT_NAME not in text, ignoring.")
            return
        text = text.replace(BOT_NAME, "").strip()

    # GPT呼び出し用メッセージ組み立て
    messages = [
        {"role": "system", "content": PERSONA_PROMPT},
        {"role": "user",   "content": text}
    ]
    logging.info(f"⏩ calling OpenAI with model={MODEL_NAME}")

    # 実際にChatGPTに問い合わせ
    try:
        resp = openai.ChatCompletion.create(
            model=MODEL_NAME,
            messages=messages
        )
        reply = resp.choices[0].message.content.strip()
    except RateLimitError:
        reply = "申し訳ありません。現在混み合っていて応答できません。"
    except Exception:
        logging.error("Error calling OpenAI:\n" + traceback.format_exc())
        reply = "すみません、回答中にエラーが発生しました。"

    # ─── ここからPush／Reply部分 ───
    try:
        if event.source.type in ("group", "room"):
            target_id = (
                event.source.group_id
                if event.source.type == "group"
                else event.source.room_id
            )
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=reply)
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply)
            )
    except LineBotApiError as e:
        logging.error(f"LineBotApiError: {e.status_code} {e.error.message}")
