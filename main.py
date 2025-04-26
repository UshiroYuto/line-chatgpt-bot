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
