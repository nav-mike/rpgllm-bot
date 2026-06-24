# RPG LLM Bot

A Telegram bot that brings your RPG character to life. Powered by an LLM, it speaks in first person *as* your character — sharing their thoughts, instincts, and reactions to whatever situation you describe. It also maintains a persistent character diary, automatically journaling significant moments in the character's own voice.

Works with any RPG world: Skyrim, Baldur's Gate, Pathfinder, homebrew, or anything else. Responds in the player's language (English or Russian).

## Features

- **Character roleplay** — the bot *is* your character, not a narrator or advisor
- **Character profiles** — name, race, class, and background shape every response
- **Persistent diary** — notable moments are saved as in-character journal entries
- **Full chat history** — conversation context is preserved per character across sessions
- **Multi-character support** — create multiple characters and switch between them

## Setup

### Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for dependency management
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- An [OpenRouter](https://openrouter.ai) API key
- A [Supabase](https://supabase.com) project

### Environment Variables

| Variable | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `RPG_LLM_OPENROUTER_API_KEY` | OpenRouter API key |
| `RPG_LLM_SUPABASE_URL` | Supabase project URL |
| `RPG_LLM_SUPABASE_PUBLISHABLE_KEY` | Supabase public (anon) key |

Copy `.env.example` to `.env` and fill in the values (or export them in your shell).

### Install & Run

```bash
uv sync
python main.py
```

### Docker

```bash
docker build -t rpgllm-bot .
docker run --env-file .env rpgllm-bot
```

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Register your Telegram account |
| `/create_character <name>` | Create a new character |
| `/list_characters` | List all your characters |
| `/use <name>` | Switch to a character |
| `/current` | Show the active character's profile |
| `/update_background <text>` | Update character background |
| `/update_race <race>` | Update character race |
| `/update_class <class>` | Update character class |
| `/add_diary <entry>` | Manually add a diary entry |
| *(any text)* | Talk to your character |

## Stack

- **Bot**: [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- **LLM**: [pydantic-ai](https://github.com/pydantic/pydantic-ai) with OpenRouter (`openrouter/owl-alpha`)
- **Database**: [Supabase](https://supabase.com) (PostgreSQL)
