# Instagram-Agent

An Instagram Agent powered by FreeLLMAPI to generate content and publish directly to Instagram via the Facebook Graph API. Supports streaming output with chain-of-thought reasoning.

## Features

- 🤖 **FreeLLMAPI Integration** — Uses FreeLLMAPI's OpenAI-compatible endpoint with auto model selection
- 📸 **Content Generation** — Generate posts, captions, hashtags, and full strategies
- 🧠 **Reasoning Mode** — Show the AI's step-by-step thinking before the answer
- ⚡ **Streaming Output** — Tokens appear in real-time as they're generated
- 🔑 **OAuth Flow** — One-command Instagram/Facebook authentication
- 📤 **Direct Publishing** — Create posts, carousels, and Reels on Instagram
- 📊 **Insights** — View post and account analytics
- 🏁 **Dry Run** — Preview generated captions without publishing
- 🔧 **Flexible Config** — Load API keys from env vars, `.env`, or `~/.config/instagram-agent/config.ini`

## Quick Start

### 1. Install

```bash
cd Instagram-Agent
pip install -e .
```

### 2. Configure your FreeLLMAPI Key

Set your FreeLLMAPI credentials via one of:

**Option A: Environment variables**
```bash
export LLM_API_KEY=your_api_key
export LLM_BASE_URL=http://localhost:3001/v1
export LLM_MODEL=auto
```

**Option B: `.env` file** (in project root)
```bash
cp .env.example .env
# Edit .env with your key and settings
```

**Option C: Config file** (`~/.config/instagram-agent/config.ini`)
```ini
[default]
LLM_API_KEY=your_api_key
LLM_BASE_URL=http://localhost:3001/v1
LLM_MODEL=auto
LLM_PROVIDER=custom
LLM_API_MODE=chat_completions
```

You can copy the example:
```bash
mkdir -p ~/.config/instagram-agent
cp config.ini.example ~/.config/instagram-agent/config.ini
# Edit with your actual key
```

### 3. Set Up Instagram Publishing (Optional)

To publish directly to Instagram, you need a Facebook Developer App and an Instagram Business/Creator account.

#### Prerequisites

1. **Instagram Business/Creator Account** — Convert your personal Instagram to a Business or Creator account in the Instagram app settings.
2. **Facebook Page** — You need a Facebook Page linked to your Instagram account.
3. **Facebook Developer App** — Create one at [https://developers.facebook.com/apps/](https://developers.facebook.com/apps/) with:
   - **Instagram Basic** product added
   - **Instagram Graph API** with `instagram_content_publish` permission
   - **Facebook Login** configured with the OAuth redirect URI: `http://localhost:21420/`

#### Configure Facebook App Credentials

Add your Facebook App ID and Secret to your config:

```bash
# Option A: Environment variables
export FB_APP_ID=your_app_id
export FB_APP_SECRET=your_app_secret

# Option B: .env file
echo "FB_APP_ID=your_app_id" >> .env
echo "FB_APP_SECRET=your_app_secret" >> .env

# Option C: config.ini
# Edit ~/.config/instagram-agent/config.ini and add:
# FB_APP_ID=your_app_id
# FB_APP_SECRET=your_app_secret
```

#### Run the OAuth Flow

```bash
# Start the OAuth flow (opens browser for Facebook login)
instagram-agent auth

# Without auto-opening the browser
instagram-agent auth --no-browser

# Custom callback port (must match your Facebook App settings)
instagram-agent auth --port 9999

# Refresh an existing long-lived token (tokens expire in 60 days)
instagram-agent auth --refresh
```

The OAuth flow will:
1. Open your browser to the Facebook consent screen
2. Ask you to grant permissions for Instagram publishing
3. Exchange the authorization code for access tokens
4. Discover your Instagram Business Account ID
5. Save the token and account ID to `~/.config/instagram-agent/config.ini`

### 4. Run

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

### 5. Publish to Instagram

```bash
# Publish a single image post (AI generates the caption)
instagram-agent publish "New product launch" --image https://example.com/photo.jpg

# Preview the caption without publishing (dry run)
instagram-agent publish "New product launch" --image https://example.com/photo.jpg --dry-run

# Publish a carousel (2-10 images)
instagram-agent publish "Travel highlights" --images https://example.com/1.jpg https://example.com/2.jpg https://example.com/3.jpg

# Publish a Reel
instagram-agent publish "Morning routine" --video https://example.com/reel.mp4

# Custom style and no hashtags
instagram-agent publish "Quick recipe" --image https://example.com/food.jpg --style casual --no-hashtags
```

### 6. Run as an HTTP API Server (Reverse Proxy)

Run the agent as a persistent HTTP server behind a reverse proxy:

```bash
# Basic usage (listens on 127.0.0.1:21420)
instagram-agent serve

# With custom OAuth redirect URI for reverse proxy
instagram-agent serve --oauth-redirect-uri https://instagram14.hotel.portnumber53.com/auth/callback

# Custom host and port
instagram-agent serve --host 0.0.0.0 --port 8080
```

#### HTTP Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check / service info |
| `GET` | `/auth/url` | Get the OAuth authorization URL |
| `GET` | `/auth/callback` | Handle OAuth callback from Facebook |
| `POST` | `/auth/refresh` | Refresh the long-lived token |
| `POST` | `/chat` | Chat with the agent (`{message, show_reasoning}`) |
| `POST` | `/post` | Generate a post (`{topic, style, include_hashtags}`) |
| `POST` | `/caption` | Generate a caption (`{description, tone}`) |
| `POST` | `/hashtags` | Generate hashtags (`{description, count}`) |
| `POST` | `/strategy` | Generate content strategy (`{niche, goals}`) |
| `POST` | `/publish` | Publish to Instagram (`{topic, image_url, image_urls, video_url, style, dry_run}`) |
| `POST` | `/image` | Generate an image (`{prompt, seed, steps, height, width, guidance}`) |
| `GET` | `/account` | Get Instagram account info |
| `GET` | `/insights` | Get insights (`?media_id=<id>` or `?account=true&period=day`) |

#### OAuth via the Server

When running behind a reverse proxy, set the OAuth redirect URI to your public URL:

```bash
instagram-agent serve --oauth-redirect-uri https://instagram14.hotel.portnumber53.com/auth/callback
```

Then visit `https://instagram14.hotel.portnumber53.com/auth/url` to get the OAuth link. After authorizing on Facebook, the callback will be handled by the server at `/auth/callback`.

### 7. View Account Info & Insights

```bash
# Show your Instagram account info
instagram-agent account

# Get insights for a specific post
instagram-agent insights --media-id 17891234567890123

# Get account-level insights
instagram-agent insights --account

# Account insights for a specific period (day, week, days_28)
instagram-agent insights --account --period week
```

## Commands

| Command | Description |
|---------|-------------|
| `chat [message]` | Interactive or one-shot chat with the agent |
| `post <topic>` | Generate an Instagram post |
| `caption <description>` | Generate an image caption |
| `hashtags <description>` | Generate hashtag set |
| `strategy <niche>` | Generate a content strategy |
| `auth` | Run Instagram/Facebook OAuth flow |
| `publish <topic>` | Generate AI content and publish to Instagram |
| `account` | Show Instagram account info |
| `insights` | View post or account insights |
| `serve` | Start HTTP API server (for reverse proxy / always-on) |

### Global Options

| Flag | Description |
|------|-------------|
| `--model <name>` | LLM model (default: `auto`) |
| `--api-key <key>` | Override API key from config |
| `--reasoning` | Show chain-of-thought reasoning before answers |

### Command-Specific Options

- `chat`: `--no-stream`, `--reasoning`
- `post`: `--style <style>`, `--no-hashtags`
- `caption`: `--tone <tone>`
- `hashtags`: `--count <n>`
- `auth`: `--port <port>`, `--no-browser`, `--refresh`
- `publish`: `--image <url>`, `--images <url> ...`, `--video <url>`, `--style <style>`, `--no-hashtags`, `--dry-run`
- `insights`: `--media-id <id>`, `--account`, `--period <period>`
- `serve`: `--port <port>`, `--host <addr>`, `--oauth-redirect-uri <uri>`

## Configuration Priority

Settings are loaded in this order (highest priority first):

1. **Environment variables** — `export LLM_API_KEY=your_api_key`
2. **`.env` file** — In the project root directory
3. **`config.ini`** — At `~/.config/instagram-agent/config.ini` with `[default]` section

## Configuration Reference

| Variable | Description | Required For |
|----------|-------------|-------------|
| `LLM_API_KEY` | FreeLLMAPI key | All commands |
| `LLM_BASE_URL` | FreeLLMAPI base URL (default: `http://localhost:3001/v1`) | All commands |
| `LLM_MODEL` | Model name (default: `auto`) | All commands |
| `LLM_PROVIDER` | Provider type (default: `custom`) | All commands |
| `LLM_API_MODE` | API mode (default: `chat_completions`) | All commands |
| `HF_TOKEN` | HuggingFace token (for FLUX.1 model downloads) | `image` |
| `FB_APP_ID` | Facebook Developer App ID | `auth` |
| `FB_APP_SECRET` | Facebook Developer App Secret | `auth`, `auth --refresh` |
| `IG_ACCESS_TOKEN` | Instagram long-lived access token | `publish`, `account`, `insights` |
| `IG_ACCOUNT_ID` | Instagram Business Account ID | `publish`, `account`, `insights` |

> **Note:** `IG_ACCESS_TOKEN` and `IG_ACCOUNT_ID` are set automatically by `instagram-agent auth`. You don't need to configure them manually unless you already have a token from another source.

## Project Structure

```
Instagram-Agent/
├── src/instagram_agent/
│   ├── __init__.py     # Package metadata
│   ├── agent.py        # Core agent with FreeLLMAPI + publishing methods
│   ├── cli.py          # CLI entry point with subcommands
│   ├── config.py       # Multi-source config loader + OAuth fields
│   ├── oauth.py        # Instagram/Facebook OAuth 2.0 flow
│   └── instagram.py    # Facebook Graph API client (containers, publish, insights)
├── config.ini.example  # Example config file
├── .env.example        # Example environment file
├── pyproject.toml      # Build config & dependencies
├── requirements.txt    # Pip dependencies
└── README.md
```

## How Publishing Works

Instagram's Content Publishing API uses a two-step process:

1. **Create a media container** — Upload the media URL and caption to Instagram's servers. Instagram processes the media (downloading, transcoding, validating).
2. **Publish the container** — Once the container status is `FINISHED`, publish it to make it live.

The `instagram-agent publish` command handles both steps automatically:
- Generates an AI caption based on your topic
- Creates the container
- Polls until processing completes
- Publishes the post

### Token Expiry

Long-lived access tokens expire after 60 days. Before expiry, refresh with:

```bash
instagram-agent auth --refresh
```

If your token has already expired, run the full OAuth flow again:

```bash
instagram-agent auth
```

## License

MIT
