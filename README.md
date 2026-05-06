# Instagram-Agent

An Instagram Agent powered by NVIDIA NIM API to generate content and post autonomously. Supports streaming output with chain-of-thought reasoning.

## Features

- 🤖 **NVIDIA NIM Integration** — Uses NVIDIA's hosted LLM models via OpenAI-compatible API
- 📸 **Content Generation** — Generate posts, captions, hashtags, and full strategies
- 🧠 **Reasoning Mode** — Show the AI's step-by-step thinking before the answer
- ⚡ **Streaming Output** — Tokens appear in real-time as they're generated
- 🔧 **Flexible Config** — Load API keys from env vars, `.env`, or `~/.config/instagram-agent/config.ini`

## Quick Start

### 1. Install

```bash
cd Instagram-Agent
pip install -e .
```

### 2. Configure your NVIDIA API Key

Get a key from [https://build.nvidia.com/](https://build.nvidia.com/). Then set it via one of:

**Option A: Environment variable**
```bash
export NVIDIA_API_KEY=nvapi-xxxxx
```

**Option B: `.env` file** (in project root)
```bash
cp .env.example .env
# Edit .env with your key
```

**Option C: Config file** (`~/.config/instagram-agent/config.ini`)
```ini
[default]
NVIDIA_API_KEY=nvapi-xxxxx
```

You can copy the example:
```bash
mkdir -p ~/.config/instagram-agent
cp config.ini.example ~/.config/instagram-agent/config.ini
# Edit with your actual key
```

### 3. Run

You can run the agent in three ways:

```bash
# After pip install -e .  (recommended)
instagram-agent chat "What are trending Instagram formats in 2025?"

# Or as a Python module
python -m instagram_agent chat "What are trending Instagram formats in 2025?"

# Or directly
python src/instagram_agent/cli.py chat "What are trending Instagram formats in 2025?"
```

```bash
# Interactive chat
instagram-agent chat

# Single message
instagram-agent chat "What are trending Instagram formats in 2025?"

# Generate a post
instagram-agent post "Launching a new coffee blend" --style casual

# Generate a caption
instagram-agent caption "Sunset photo from Bali beach" --tone witty

# Generate hashtags
instagram-agent hashtags "Vegan recipe reel" --count 20

# Content strategy
instagram-agent strategy fitness --goals engagement

# With reasoning visible
instagram-agent post "SaaS product launch" --reasoning
```

## Commands

| Command | Description |
|---------|-------------|
| `chat [message]` | Interactive or one-shot chat with the agent |
| `post <topic>` | Generate an Instagram post |
| `caption <description>` | Generate an image caption |
| `hashtags <description>` | Generate hashtag set |
| `strategy <niche>` | Generate a content strategy |

### Global Options

| Flag | Description |
|------|-------------|
| `--model <name>` | NVIDIA NIM model (default: `meta/llama-3.3-70b-instruct`) |
| `--api-key <key>` | Override API key from config |
| `--reasoning` | Show chain-of-thought reasoning before answers |

### Command-Specific Options

- `post`: `--style <style>`, `--no-hashtags`
- `caption`: `--tone <tone>`
- `hashtags`: `--count <n>`

## Configuration Priority

Settings are loaded in this order (highest priority first):

1. **Environment variables** — `export NVIDIA_API_KEY=nvapi-xxxxx`
2. **`.env` file** — In the project root directory
3. **`config.ini`** — At `~/.config/instagram-agent/config.ini` with `[default]` section

## Project Structure

```
Instagram-Agent/
├── src/instagram_agent/
│   ├── __init__.py       # Package metadata
│   ├── agent.py          # Core agent with NVIDIA NIM streaming
│   ├── cli.py            # CLI entry point with subcommands
│   └── config.py         # Multi-source config loader
├── config.ini.example    # Example config file
├── .env.example          # Example environment file
├── pyproject.toml        # Build config & dependencies
├── requirements.txt      # Pip dependencies
└── README.md
```

## License

MIT
