import os
import logging
from typing import Any, List, cast
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
from supabase import create_client, Client
from pydantic_ai import Agent, ModelMessage, Tool
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

supabase_client: Client = create_client(
    supabase_url=os.environ["RPG_LLM_SUPABASE_URL"],
    supabase_key=os.environ["RPG_LLM_SUPABASE_PUBLISHABLE_KEY"],
)

model = OpenRouterModel(
    "openrouter/owl-alpha",
    provider=OpenRouterProvider(api_key=os.environ["RPG_LLM_OPENROUTER_API_KEY"]),
)

SYSTEM_PROMPT = """
    You are a deep roleplay companion for RPG games. Your purpose is to help the player stay fully
    in character and make decisions that fit who their character is - not just what's optimal.

    **How you work:**
    - When the player shares a situation, screenshot, or decision they face in their game, you
      analyze it through the lens of their character: their background, race, class, personality,
      and history.
    - Before advising, always retrieve the character's profile (name, background, race, class) and
      relevant diary entries using the available tools. Don't guess - look it up.
    - Give advice as a voice that knows this character deeply. Suggest what *this character* would do,
      feel, or say - not just what's mechanically smart.
    - When a significant event happens or a notable decision is made, save a record to the character's
      diary using the diary tool. Keep entries concise and written from the character's perspective,
      like a journal.

    **Language:**
    Respond in the same language the player uses - English or Russian. Switch if they switch.

    **Tone:**
    Match the gravity of the situation. A tense combat choice deserves urgency. A moral dilemma
    deserves weight. Keep responses focused - no padding, no unnecessary summaries.

    **Scope:**
    You work with any RPG - Skyrim, Baldur's Gate, Pathfinder, or others. Adapt your framing to
    the setting the player describes.
"""


def get_chat_id(update: Update) -> int:
    """
    Extract the chat id from update object.
    Raises RuntimeError if the id is None.
    """
    chat_id: int | None = getattr(update.effective_chat, "id", None)

    if not chat_id:
        raise RuntimeError("chat_id cannot be None")

    return chat_id


def get_user_id(update: Update) -> int:
    """
    Extract the user id from update object.
    Raises RuntimeError of the id is None.
    """
    user_id: int | None = getattr(update.effective_user, "id", None)

    if not user_id:
        raise RuntimeError("user_id cannot be None")

    return user_id


def error_message(e: Exception) -> str:
    """
    Extract an error message from the exception.
    """
    error_msg = str(e) or type(e).__name__
    print(error_msg)
    return error_msg


def current_user(update: Update) -> dict[str, Any]:
    """
    Get the current user from supabase.
    """
    user_id = get_user_id(update)

    response = (
        supabase_client.table("users")
        .select("*")
        .eq("telegram_id", str(user_id))
        .limit(1)
        .execute()
    )

    result: dict[str, Any] = cast(dict[str, Any], response.data[0])

    return result


def fetch_messages(character_id: int) -> list[dict[str, Any]]:
    """
    Fetch the whole chat history.
    """

    response = (
        supabase_client.table("chat")
        .select("*")
        .eq("character_id", character_id)
        .order("created_at")
        .execute()
    )
    messages = [cast(dict[str, Any], item) for item in response.data]

    return messages


def add_message(
    messages: List[dict[str, Any]], message: dict[str, Any]
) -> List[dict[str, Any]]:
    """
    Insert a message to chat table.
    """
    response = (
        supabase_client.table("chat")
        .insert(
            {
                "character_id": message["character_id"],
                "content": message["content"],
                "role": message["role"],
            }
        )
        .select("*")
        .execute()
    )

    got: dict[str, Any] = cast(dict[str, Any], response.data[0])

    messages.append(got)

    return messages


def to_history(messages: List[dict[str, Any]]) -> List[ModelMessage]:
    """
    Convert list of message to agent history.
    """
    history: List[ModelMessage] = []

    for item in messages:
        if item["role"] == "user":
            history.append(
                ModelRequest(parts=[UserPromptPart(content=item["content"])])
            )
        elif item["role"] == "model":
            history.append(ModelResponse(parts=[TextPart(content=item["content"])]))

    return history


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start command
    Usage: /start
    """
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)

    supabase_client.table("users").upsert(
        {"telegram_id": user_id}, on_conflict="telegram_id", ignore_duplicates=True
    ).execute()

    await context.bot.send_message(chat_id=chat_id, text="I'm bot, please talk to me!")


async def create_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Create a new character
    Usage: /create_character name
    """

    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    value = getattr(update.message, "text", "").partition(" ")[2]

    message = f"Character {value} has been saved."
    try:
        if not value:
            raise ValueError(
                "Character's name cannot be empty. Please use /create_character Name"
            )

        supabase_client.table("characters").insert(
            {"user_id": str(user_id), "name": value.strip()}
        ).execute()
    except Exception as e:
        message = error_message(e)
    finally:
        await context.bot.send_message(chat_id=chat_id, text=message)


async def list_characters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Retrieve the list of user's characters
    Usage: /list_characters
    """

    chat_id = get_chat_id(update)
    user_id = get_user_id(update)

    message = ""
    try:
        response = (
            supabase_client.table("characters")
            .select("*")
            .eq("user_id", str(user_id))
            .execute()
        )
        items: List[str] = [
            f"{idx + 1}) {cast(dict[str, Any], item)['name']}"
            for idx, item in enumerate(response.data)
        ]
        message = "\n".join(items)
    except Exception as e:
        message = error_message(e)
    finally:
        await context.bot.send_message(chat_id=chat_id, text=message)


async def use_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Select one of the characters for active usage.
    Usage: /use Name
    """

    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    value = getattr(update.message, "text", "").partition(" ")[2]

    message = f"Character {value} has been selected."
    try:
        if not value:
            raise ValueError("Character's name cannot be empty. Please use /use Name")

        response = (
            supabase_client.table("characters")
            .select("*")
            .eq("name", value.strip())
            .eq("user_id", str(user_id))
            .limit(1)
            .execute()
        )
        character = cast(dict[str, Any], response.data[0])

        supabase_client.table("users").update(
            {"current_character": character["id"]}
        ).eq("telegram_id", str(user_id)).execute()
    except Exception as e:
        message = error_message(e)
    finally:
        await context.bot.send_message(chat_id=chat_id, text=message)


async def current_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show the current character.
    Usage: /current
    """

    chat_id = get_chat_id(update)
    user = current_user(update)

    message = "Character is not selected"
    try:
        response = (
            supabase_client.table("characters")
            .select("*")
            .eq("id", user["current_character"])
            .execute()
        )

        character = cast(dict[str, Any], response.data[0])
        if not character:
            raise ValueError("Character is not selected")

        message = f"Currrent character is {character['name']}"
    except Exception as e:
        message = error_message(e)
    finally:
        await context.bot.send_message(chat_id=chat_id, text=message)


async def update_background(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Update the character background.
    Usage: /update_background Text
    """

    chat_id = get_chat_id(update)
    user = current_user(update)
    value = getattr(update.message, "text", "").partition(" ")[2].strip()

    try:
        if not value:
            raise ValueError(
                "Background cannot be empty. Please use /update_background Text"
            )

        supabase_client.table("characters").update({"background": value}).eq(
            "id", user["current_character"]
        ).execute()
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=error_message(e))


async def update_race(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Update the character race.
    Usage: /update_race Text
    """

    chat_id = get_chat_id(update)
    user = current_user(update)
    value = getattr(update.message, "text", "").partition(" ")[2].strip()

    try:
        if not value:
            raise ValueError("Race cannot be empty. Please use /update_race Text")

        supabase_client.table("characters").update({"race": value}).eq(
            "id", user["current_character"]
        ).execute()
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=error_message(e))


async def add_diary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Save a record to character's diary.
    Usage: /add_diary Text
    """

    chat_id = get_chat_id(update)
    user = current_user(update)
    value = getattr(update.message, "text", "").partition(" ")[2].strip()

    try:
        if not value:
            raise ValueError("Diary record cannot be empty. Please use /add_diary Text")

        supabase_client.table("diary").insert(
            {"character": user["current_character"], "message": value}
        ).execute()
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=error_message(e))


def get_character(id: int) -> dict[str, Any]:
    """
    Get character from db by id.
    """
    response = supabase_client.table("characters").select("*").eq("id", id).execute()

    return cast(dict[str, Any], response.data[0])


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Simple chat interface.
    """

    chat_id = get_chat_id(update)

    def get_diary_records(**kwargs) -> List[dict[str, Any]]:
        limit = kwargs["limit"]

        response = (
            supabase_client.table("diary")
            .select("*")
            .eq("character", character["id"])
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        return [cast(dict[str, Any], item) for item in response.data]

    tool = Tool.from_schema(
        function=get_diary_records,
        name="get_diary_records",
        description="Get last limit records from character's diary.",
        json_schema={
            "additionalProperties": False,
            "properties": {
                "limit": {
                    "description": "amout of requested diary records",
                    "type": "integeger",
                },
            },
            "required": ["limit"],
            "type": "object",
        },
        takes_ctx=False,
    )

    agent = Agent(model, deps_type=dict, system_prompt=SYSTEM_PROMPT, tools=[tool])
    message = "<empty>"

    try:
        user = current_user(update)
        character = get_character(user["current_character"])

        @agent.tool_plain()
        def get_character_background() -> str:
            return character["background"]

        @agent.tool_plain()
        def get_character_name() -> str:
            return character["name"]

        @agent.tool_plain()
        def get_character_race() -> str:
            return character["race"]

        @agent.tool_plain()
        def get_character_class() -> str:
            return character["class"]

        if not user["current_character"]:
            raise ValueError("Please select a character first by /use Name")

        value = getattr(update.message, "text", "").strip()

        messages = fetch_messages(user["current_character"])

        history: list[ModelMessage] = to_history(messages)

        if not value:
            raise ValueError("A message cannot be empty.")

        response = await agent.run(
            value,
            message_history=history,
            deps={
                "name": character["name"],
                "background": character["background"],
                "race": character["race"],
                "class": character["class"],
            },
        )

        agent_message: dict[str, Any] = {
            "content": response.output,
            "role": "model",
            "character_id": user["current_character"],
        }
        user_message: dict[str, Any] = {
            "content": value,
            "role": "user",
            "character_id": user["current_character"],
        }
        messages = add_message(messages, user_message)
        messages = add_message(messages, agent_message)
        message = f"agent: {response.output}"
    except Exception as e:
        message = error_message(e)
    finally:
        await context.bot.send_message(chat_id=chat_id, text=message)


if __name__ == "__main__":
    application = ApplicationBuilder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()

    start_handler = CommandHandler("start", start)
    create_character_handler = CommandHandler("create_character", create_character)
    list_characters_handler = CommandHandler("list_characters", list_characters)
    use_character_hanlder = CommandHandler("use", use_character)
    current_character_handler = CommandHandler("current", current_character)
    update_background_handler = CommandHandler("update_background", update_background)
    update_race_handler = CommandHandler("update_race", update_race)
    add_diary_handler = CommandHandler("add_diary", add_diary)

    chat_hanlder = MessageHandler(filters.TEXT, chat)

    application.add_handler(start_handler)
    application.add_handler(create_character_handler)
    application.add_handler(list_characters_handler)
    application.add_handler(use_character_hanlder)
    application.add_handler(current_character_handler)
    application.add_handler(update_background_handler)
    application.add_handler(update_race_handler)
    application.add_handler(add_diary_handler)
    application.add_handler(chat_hanlder)

    application.run_polling()
