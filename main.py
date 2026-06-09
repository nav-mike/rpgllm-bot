import os
import logging
from uuid import uuid4
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from supabase import create_client, Client

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

supabase_client: Client = create_client(
    supabase_url=os.environ["RPG_LLM_SUPABASE_URL"],
    supabase_key=os.environ["RPG_LLM_SUPABASE_PUBLISHABLE_KEY"],
)


def get_chat_id(update: Update) -> int:
    """
    Extract the chat id from update object.
    Raises RuntimeError if the id is None.
    """
    chat_id: int | None = getattr(update.effective_chat, "id", None)

    if not chat_id:
        raise RuntimeError("chat_id cannot be None")

    return chat_id


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start command
    Usage: /start
    """
    chat_id = get_chat_id(update)

    await context.bot.send_message(chat_id=chat_id, text="I'm bot, please talk to me!")


async def create_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Create a new character
    Usage: /create_character name
    """

    chat_id = get_chat_id(update)
    user_id: int | None = getattr(update.effective_user, "id", None)
    value = getattr(update.message, "text", "").partition(" ")[2]

    if not user_id:
        raise RuntimeError("user_id cannot be None")

    message = f"Character {value} has been saved."
    try:
        if not value:
            raise ValueError(
                "Character's name cannot be empty. Please use /create_character Name"
            )

        supabase_client.table("characters").insert(
            {"user_id": str(user_id), "name": value}
        )
    except Exception as e:
        message = f"{e}"
    finally:
        await context.bot.send_message(chat_id=chat_id, text=message)


if __name__ == "__main__":
    application = ApplicationBuilder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()

    response = supabase_client.table("characters").select("*").execute()

    print("response: ", response.data)

    start_handler = CommandHandler("start", start)
    application.add_handler(start_handler)

    application.run_polling()
