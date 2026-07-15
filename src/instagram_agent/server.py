"""HTTP API server for Instagram-Agent.

Runs a Flask web server that exposes all agent functionality via JSON endpoints.
Designed to run behind a reverse proxy (e.g. at https://instagram14.hotel.portnumber53.com/).
"""

import os
from typing import Optional

from flask import Flask, request, jsonify, send_file

from instagram_agent.agent import InstagramAgent
from instagram_agent.config import (
    get_fb_app_id,
    get_fb_app_secret,
    get_llm_base_url,
    get_llm_model,
    save_token_to_config,
    CONFIG_FILE,
)
from instagram_agent.oauth import (
    generate_auth_url,
    _exchange_code_for_token,
    _exchange_for_long_lived_token,
    _discover_ig_account_id,
    refresh_long_lived_token,
    IG_SCOPES,
)

DEFAULT_PORT = 21420


def create_app(agent: Optional[InstagramAgent] = None, oauth_redirect_uri: Optional[str] = None) -> Flask:
    """Create and configure the Flask app.

    Args:
        agent: Pre-configured InstagramAgent instance. If None, created lazily.
        oauth_redirect_uri: Override OAuth redirect URI (e.g. for reverse proxy).
            Defaults to http://localhost:{port}/auth/callback.
    """
    app = Flask(__name__)
    app.config["_agent"] = agent
    app.config["_oauth_redirect_uri"] = oauth_redirect_uri

    def get_agent() -> InstagramAgent:
        if app.config["_agent"] is None:
            app.config["_agent"] = InstagramAgent()
        return app.config["_agent"]

    # ── Dashboard / info ──────────────────────────────────────────

    @app.route("/", methods=["GET"])
    def dashboard():
        return _dashboard_html()

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "service": "instagram-agent",
            "status": "running",
            "model": get_llm_model(),
            "base_url": get_llm_base_url(),
        })

    # ── OAuth ──────────────────────────────────────────────────────

    @app.route("/auth/status", methods=["GET"])
    def auth_status():
        """Check if Instagram account is connected."""
        from instagram_agent.config import get_ig_access_token, get_ig_account_id
        token = get_ig_access_token()
        account_id = get_ig_account_id()
        connected = bool(token and account_id)
        return jsonify({
            "connected": connected,
            "account_id": account_id,
        })

    @app.route("/auth/url", methods=["GET"])
    def auth_url():
        """Return the OAuth URL to visit in a browser."""
        app_id = get_fb_app_id()
        if not app_id:
            return jsonify({"error": "FB_APP_ID not configured"}), 400

        redirect_uri = app.config["_oauth_redirect_uri"] or f"http://localhost:{DEFAULT_PORT}/auth/callback"
        url = generate_auth_url(app_id, redirect_uri)
        return jsonify({"auth_url": url, "redirect_uri": redirect_uri})

    @app.route("/auth/callback", methods=["GET"])
    def auth_callback():
        """Handle the OAuth callback from Facebook."""
        code = request.args.get("code")
        error = request.args.get("error")
        error_desc = request.args.get("error_description")

        if error:
            return _auth_result_html(False, f"{error}: {error_desc or ''}")

        if not code:
            return _auth_result_html(False, "No authorization code received.")

        app_id = get_fb_app_id()
        app_secret = get_fb_app_secret()
        if not app_id or not app_secret:
            return _auth_result_html(False, "FB_APP_ID and FB_APP_SECRET not configured.")

        redirect_uri = app.config["_oauth_redirect_uri"] or f"http://localhost:{DEFAULT_PORT}/auth/callback"

        try:
            short_token = _exchange_code_for_token(app_id, app_secret, code, redirect_uri)
            long_token = _exchange_for_long_lived_token(app_id, app_secret, short_token)
            ig_account_id = _discover_ig_account_id(long_token)

            save_token_to_config("IG_ACCESS_TOKEN", long_token)
            save_token_to_config("IG_ACCOUNT_ID", ig_account_id)

            return _auth_result_html(True, ig_account_id)
        except SystemExit as e:
            return _auth_result_html(False, str(e))
        except Exception as e:
            return _auth_result_html(False, str(e))

    @app.route("/auth/refresh", methods=["POST"])
    def auth_refresh():
        """Refresh the long-lived Instagram token."""
        try:
            new_token = refresh_long_lived_token()
            return jsonify({"status": "success", "token": new_token[:12] + "..."})
        except SystemExit as e:
            return jsonify({"error": str(e)}), 500

    # ── Chat ───────────────────────────────────────────────────────

    @app.route("/chat", methods=["POST"])
    def chat():
        data = request.get_json(force=True)
        message = data.get("message")
        if not message:
            return jsonify({"error": "message is required"}), 400

        show_reasoning = data.get("show_reasoning", False)
        stream = data.get("stream", False)

        agent = get_agent()
        response = agent.chat(message, stream=stream, show_reasoning=show_reasoning)
        return jsonify({"response": response})

    # ── Post generation ────────────────────────────────────────────

    @app.route("/post", methods=["POST"])
    def post():
        data = request.get_json(force=True)
        topic = data.get("topic")
        if not topic:
            return jsonify({"error": "topic is required"}), 400

        agent = get_agent()
        result = agent.generate_post(
            topic=topic,
            style=data.get("style", "professional"),
            include_hashtags=data.get("include_hashtags", True),
            show_reasoning=data.get("show_reasoning", False),
            stream=False,
        )
        return jsonify({"post": result})

    # ── Caption generation ─────────────────────────────────────────

    @app.route("/caption", methods=["POST"])
    def caption():
        data = request.get_json(force=True)
        description = data.get("description")
        if not description:
            return jsonify({"error": "description is required"}), 400

        agent = get_agent()
        result = agent.generate_caption(
            image_description=description,
            tone=data.get("tone", "engaging"),
            show_reasoning=data.get("show_reasoning", False),
        )
        return jsonify({"caption": result})

    # ── Hashtag generation ─────────────────────────────────────────

    @app.route("/hashtags", methods=["POST"])
    def hashtags():
        data = request.get_json(force=True)
        description = data.get("description")
        if not description:
            return jsonify({"error": "description is required"}), 400

        agent = get_agent()
        result = agent.generate_hashtags(
            content_description=description,
            count=data.get("count", 15),
            show_reasoning=data.get("show_reasoning", False),
        )
        return jsonify({"hashtags": result})

    # ── Content strategy ───────────────────────────────────────────

    @app.route("/strategy", methods=["POST"])
    def strategy():
        data = request.get_json(force=True)
        niche = data.get("niche")
        if not niche:
            return jsonify({"error": "niche is required"}), 400

        agent = get_agent()
        result = agent.content_strategy(
            niche=niche,
            goals=data.get("goals", "growth"),
            show_reasoning=data.get("show_reasoning", False),
        )
        return jsonify({"strategy": result})

    # ── Publish ────────────────────────────────────────────────────

    @app.route("/publish", methods=["POST"])
    def publish():
        data = request.get_json(force=True)
        topic = data.get("topic")
        if not topic:
            return jsonify({"error": "topic is required"}), 400

        agent = get_agent()
        style = data.get("style", "professional")
        include_hashtags = data.get("include_hashtags", True)
        dry_run = data.get("dry_run", False)
        show_reasoning = data.get("show_reasoning", False)

        try:
            if data.get("video_url"):
                result = agent.publish_reel(
                    video_url=data["video_url"],
                    topic=topic,
                    style=style,
                    include_hashtags=include_hashtags,
                    dry_run=dry_run,
                    show_reasoning=show_reasoning,
                )
            elif data.get("image_urls") and len(data["image_urls"]) > 1:
                result = agent.publish_carousel(
                    image_urls=data["image_urls"],
                    topic=topic,
                    style=style,
                    include_hashtags=include_hashtags,
                    dry_run=dry_run,
                    show_reasoning=show_reasoning,
                )
            elif data.get("image_url"):
                result = agent.publish_post(
                    image_url=data["image_url"],
                    topic=topic,
                    style=style,
                    include_hashtags=include_hashtags,
                    dry_run=dry_run,
                    show_reasoning=show_reasoning,
                )
            else:
                return jsonify({"error": "Specify image_url, image_urls, or video_url"}), 400

            return jsonify(result)
        except SystemExit as e:
            return jsonify({"error": str(e)}), 500

    # ── Image generation ───────────────────────────────────────────

    @app.route("/image", methods=["POST"])
    def image():
        data = request.get_json(force=True)
        prompt = data.get("prompt")
        if not prompt:
            return jsonify({"error": "prompt is required"}), 400

        agent = get_agent()
        try:
            image_path = agent.generate_image(
                prompt=prompt,
                seed=data.get("seed"),
                num_inference_steps=data.get("steps", 4),
                height=data.get("height", 1024),
                width=data.get("width", 1024),
                guidance=data.get("guidance", 4.0),
                output_dir=data.get("output_dir"),
                filename=data.get("filename"),
                show_reasoning=data.get("show_reasoning", False),
            )
            return jsonify({"image_path": image_path})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ── Account ────────────────────────────────────────────────────

    @app.route("/account", methods=["GET"])
    def account():
        from instagram_agent.instagram import InstagramClient
        try:
            client = InstagramClient()
            info = client.get_account_info()
            return jsonify(info)
        except SystemExit as e:
            return jsonify({"error": str(e)}), 500

    # ── Insights ───────────────────────────────────────────────────

    @app.route("/insights", methods=["GET"])
    def insights():
        from instagram_agent.instagram import InstagramClient
        media_id = request.args.get("media_id")
        is_account = request.args.get("account", "").lower() in ("1", "true", "yes")
        period = request.args.get("period", "day")

        try:
            client = InstagramClient()
            if media_id:
                result = client.get_media_insights(media_id)
            elif is_account:
                result = client.get_account_insights(period=period)
            else:
                return jsonify({"error": "Specify media_id or account=true"}), 400
            return jsonify(result)
        except SystemExit as e:
            return jsonify({"error": str(e)}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


def _auth_result_html(success: bool, detail: str) -> str:
    """Return an HTML page for OAuth callback results, with auto-redirect to dashboard."""
    if success:
        icon = "✅"
        title = "Connected!"
        msg = f"Your Instagram account is now connected."
        submsg = f"Account ID: {detail}"
        color = "var(--success)"
    else:
        icon = "❌"
        title = "Connection Failed"
        msg = "Could not connect your Instagram account."
        submsg = detail
        color = "var(--error)"

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Instagram Agent — OAuth Result</title>
<meta http-equiv="refresh" content="3;url=/">
<style>
:root {{
  --bg: #0a0a0f;
  --surface: #131318;
  --surface2: #1a1a22;
  --border: #2a2a35;
  --text: #e8e8f0;
  --muted: #8888a0;
  --accent: #e1306c;
  --accent2: #c13584;
  --success: #4ade80;
  --error: #f87171;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg); color: var(--text);
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
}}
.card {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 16px; padding: 40px; text-align: center;
  max-width: 420px; width: 90%;
}}
.icon {{ font-size: 48px; margin-bottom: 16px; }}
h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 8px; }}
.msg {{ font-size: 15px; color: var(--muted); margin-bottom: 6px; }}
.submsg {{
  font-size: 13px; color: {color};
  background: var(--surface2); border-radius: 8px;
  padding: 10px 14px; margin-top: 12px;
  word-break: break-all;
}}
.redirect {{
  font-size: 13px; color: var(--muted); margin-top: 20px;
}}
.redirect a {{ color: var(--accent); text-decoration: none; }}
.spinner {{
  display: inline-block; width: 14px; height: 14px;
  border: 2px solid var(--border); border-top-color: var(--accent);
  border-radius: 50%; animation: spin 0.6s linear infinite;
  vertical-align: middle; margin-right: 6px;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>
<div class="card">
  <div class="icon">{icon}</div>
  <h1 style="color: {color}">{title}</h1>
  <div class="msg">{msg}</div>
  <div class="submsg">{submsg}</div>
  <div class="redirect">
    <span class="spinner"></span> Redirecting to dashboard in 3 seconds...
    <br><a href="/">Go to dashboard now</a>
  </div>
</div>
</body>
</html>'''


def _dashboard_html() -> str:
    """Return the HTML dashboard page."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Instagram Agent</title>
<style>
:root {
  --bg: #0a0a0f;
  --surface: #131318;
  --surface2: #1a1a22;
  --border: #2a2a35;
  --text: #e8e8f0;
  --muted: #8888a0;
  --accent: #e1306c;
  --accent2: #c13584;
  --success: #4ade80;
  --warn: #fbbf24;
  --error: #f87171;
  --radius: 12px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  line-height: 1.6;
}
.container { max-width: 900px; margin: 0 auto; padding: 24px 16px; }

/* Header */
.header {
  display: flex; align-items: center; gap: 14px;
  padding: 20px 0; border-bottom: 1px solid var(--border); margin-bottom: 28px;
}
.header .logo {
  width: 44px; height: 44px; border-radius: 12px;
  background: linear-gradient(135deg, var(--accent), var(--accent2), #f77737);
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; flex-shrink: 0;
}
.header h1 { font-size: 22px; font-weight: 700; }
.header .subtitle { font-size: 13px; color: var(--muted); }

/* Status badge */
.status-badge {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 14px; border-radius: 100px; font-size: 13px; font-weight: 600;
}
.status-badge.connected { background: rgba(74,222,128,0.12); color: var(--success); }
.status-badge.disconnected { background: rgba(248,113,113,0.12); color: var(--error); }
.status-badge .dot {
  width: 8px; height: 8px; border-radius: 50%;
}
.status-badge.connected .dot { background: var(--success); box-shadow: 0 0 8px var(--success); }
.status-badge.disconnected .dot { background: var(--error); }

/* Cards */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  margin-bottom: 20px;
}
.card h2 { font-size: 16px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
.card .desc { font-size: 14px; color: var(--muted); margin-bottom: 16px; }

/* Buttons */
.btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 20px; border-radius: 8px; border: none;
  font-size: 14px; font-weight: 600; cursor: pointer;
  transition: all 0.15s ease;
}
.btn-primary {
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: white;
}
.btn-primary:hover { opacity: 0.9; transform: translateY(-1px); }
.btn-secondary {
  background: var(--surface2); color: var(--text); border: 1px solid var(--border);
}
.btn-secondary:hover { border-color: var(--muted); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
.btn-sm { padding: 6px 14px; font-size: 13px; }

/* Forms */
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 6px; }
.form-group input, .form-group textarea, .form-group select {
  width: 100%; padding: 10px 12px;
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 8px; color: var(--text); font-size: 14px;
  font-family: inherit;
}
.form-group input:focus, .form-group textarea:focus, .form-group select:focus {
  outline: none; border-color: var(--accent);
}
.form-group textarea { resize: vertical; min-height: 80px; }
.form-row { display: flex; gap: 12px; }
.form-row .form-group { flex: 1; }

/* Output */
.output {
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 8px; padding: 16px; margin-top: 14px;
  font-size: 14px; white-space: pre-wrap; word-break: break-word;
  max-height: 400px; overflow-y: auto;
  display: none;
}
.output.show { display: block; }
.output.error { border-color: var(--error); color: var(--error); }
.output.success { border-color: var(--success); }

/* Account info */
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.info-item {
  background: var(--surface2); border-radius: 8px; padding: 12px 16px;
}
.info-item .label { font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.info-item .value { font-size: 15px; font-weight: 600; }

/* Tabs */
.tabs { display: flex; gap: 4px; margin-bottom: 20px; border-bottom: 1px solid var(--border); }
.tab {
  padding: 10px 18px; font-size: 14px; font-weight: 500;
  color: var(--muted); cursor: pointer; border-bottom: 2px solid transparent;
  transition: all 0.15s ease;
}
.tab:hover { color: var(--text); }
.tab.active { color: var(--text); border-bottom-color: var(--accent); }
.tab-content { display: none; }
.tab-content.active { display: block; }

/* Loading spinner */
.spinner {
  display: inline-block; width: 16px; height: 16px;
  border: 2px solid var(--border); border-top-color: var(--accent);
  border-radius: 50%; animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.hidden { display: none !important; }
</style>
</head>
<body>
<div class="container">
  <!-- Header -->
  <div class="header">
    <div class="logo">📷</div>
    <div>
      <h1>Instagram Agent</h1>
      <div class="subtitle">AI-powered content generation & publishing</div>
    </div>
    <div style="margin-left:auto">
      <span id="status-badge" class="status-badge disconnected">
        <span class="dot"></span>
        <span id="status-text">Checking...</span>
      </span>
    </div>
  </div>

  <!-- Connection Card -->
  <div id="connection-card" class="card">
    <h2>🔗 Instagram Connection</h2>
    <div id="connection-content">
      <div class="desc">Connect your Instagram Business/Creator account to enable publishing via the Facebook Graph API.</div>
      <button class="btn btn-primary" id="connect-btn" onclick="startOAuth()">
        Connect Instagram Account
      </button>
    </div>
  </div>

  <!-- Account Info (shown when connected) -->
  <div id="account-card" class="card hidden">
    <h2>📸 Account Info</h2>
    <div class="info-grid" id="account-info"></div>
    <div style="margin-top:16px; display:flex; gap:10px;">
      <button class="btn btn-secondary btn-sm" onclick="loadAccount()">Refresh Info</button>
      <button class="btn btn-secondary btn-sm" onclick="refreshToken()">Refresh Token</button>
    </div>
  </div>

  <!-- Tools (shown when connected) -->
  <div id="tools-section" class="hidden">
    <div class="tabs">
      <div class="tab active" onclick="switchTab('generate')">Generate</div>
      <div class="tab" onclick="switchTab('publish')">Publish</div>
      <div class="tab" onclick="switchTab('image')">Image</div>
      <div class="tab" onclick="switchTab('insights')">Insights</div>
    </div>

    <!-- Generate Tab -->
    <div id="tab-generate" class="tab-content active">
      <div class="card">
        <h2>✍️ Generate Content</h2>
        <div class="form-row">
          <div class="form-group">
            <label>Type</label>
            <select id="gen-type">
              <option value="post">Post</option>
              <option value="caption">Caption</option>
              <option value="hashtags">Hashtags</option>
              <option value="strategy">Strategy</option>
              <option value="chat">Chat</option>
            </select>
          </div>
          <div class="form-group" id="gen-style-group">
            <label>Style</label>
            <select id="gen-style">
              <option value="professional">Professional</option>
              <option value="casual">Casual</option>
              <option value="funny">Funny</option>
              <option value="inspirational">Inspirational</option>
            </select>
          </div>
        </div>
        <div class="form-group">
          <label id="gen-input-label">Topic</label>
          <textarea id="gen-input" placeholder="Enter topic or message..."></textarea>
        </div>
        <button class="btn btn-primary" id="gen-btn" onclick="generateContent()">Generate</button>
        <div class="output" id="gen-output"></div>
      </div>
    </div>

    <!-- Publish Tab -->
    <div id="tab-publish" class="tab-content">
      <div class="card">
        <h2>📤 Publish to Instagram</h2>
        <div class="form-group">
          <label>Topic (drives AI caption)</label>
          <input type="text" id="pub-topic" placeholder="e.g. New product launch">
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Style</label>
            <select id="pub-style">
              <option value="professional">Professional</option>
              <option value="casual">Casual</option>
              <option value="funny">Funny</option>
              <option value="inspirational">Inspirational</option>
            </select>
          </div>
          <div class="form-group">
            <label>Media Type</label>
            <select id="pub-media-type">
              <option value="image">Single Image</option>
              <option value="carousel">Carousel</option>
              <option value="reel">Reel</option>
            </select>
          </div>
        </div>
        <div class="form-group" id="pub-image-group">
          <label>Image URL</label>
          <input type="text" id="pub-image-url" placeholder="https://example.com/photo.jpg">
        </div>
        <div class="form-group hidden" id="pub-images-group">
          <label>Image URLs (one per line, 2-10)</label>
          <textarea id="pub-image-urls" placeholder="https://example.com/1.jpg&#10;https://example.com/2.jpg"></textarea>
        </div>
        <div class="form-group hidden" id="pub-video-group">
          <label>Video URL</label>
          <input type="text" id="pub-video-url" placeholder="https://example.com/reel.mp4">
        </div>
        <div class="form-group">
          <label>
            <input type="checkbox" id="pub-dry-run" checked> Dry Run (preview without publishing)
          </label>
        </div>
        <button class="btn btn-primary" id="pub-btn" onclick="publishContent()">Publish</button>
        <div class="output" id="pub-output"></div>
      </div>
    </div>

    <!-- Image Tab -->
    <div id="tab-image" class="tab-content">
      <div class="card">
        <h2>🎨 Generate Image</h2>
        <div class="form-group">
          <label>Prompt</label>
          <textarea id="img-prompt" placeholder="Describe the image to generate..."></textarea>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Width</label>
            <input type="number" id="img-width" value="1024">
          </div>
          <div class="form-group">
            <label>Height</label>
            <input type="number" id="img-height" value="1024">
          </div>
          <div class="form-group">
            <label>Steps</label>
            <input type="number" id="img-steps" value="4">
          </div>
        </div>
        <button class="btn btn-primary" id="img-btn" onclick="generateImage()">Generate Image</button>
        <div class="output" id="img-output"></div>
      </div>
    </div>

    <!-- Insights Tab -->
    <div id="tab-insights" class="tab-content">
      <div class="card">
        <h2>📊 Insights</h2>
        <div class="form-row">
          <div class="form-group">
            <label>Period</label>
            <select id="ins-period">
              <option value="day">Day</option>
              <option value="week">Week</option>
              <option value="days_28">28 Days</option>
            </select>
          </div>
        </div>
        <button class="btn btn-primary" onclick="loadInsights()">Load Account Insights</button>
        <div class="output" id="ins-output"></div>
      </div>
    </div>
  </div>
</div>

<script>
const $ = (id) => document.getElementById(id);

// ── Status check on load ──────────────────────────────────
async function checkStatus() {
  try {
    const res = await fetch('/auth/status');
    const data = await res.json();
    if (data.connected) {
      $('status-badge').className = 'status-badge connected';
      $('status-text').textContent = 'Connected';
      $('connection-card').classList.add('hidden');
      $('account-card').classList.remove('hidden');
      $('tools-section').classList.remove('hidden');
      loadAccount();
    } else {
      $('status-badge').className = 'status-badge disconnected';
      $('status-text').textContent = 'Not Connected';
    }
  } catch (e) {
    $('status-text').textContent = 'Error';
  }
}

// ── OAuth ─────────────────────────────────────────────────
async function startOAuth() {
  $('connect-btn').disabled = true;
  $('connect-btn').innerHTML = '<span class="spinner"></span> Getting URL...';
  try {
    const res = await fetch('/auth/url');
    const data = await res.json();
    if (data.auth_url) {
      window.location.href = data.auth_url;
    } else {
      alert('Error: ' + (data.error || 'Could not get OAuth URL'));
      $('connect-btn').disabled = false;
      $('connect-btn').textContent = 'Connect Instagram Account';
    }
  } catch (e) {
    alert('Error: ' + e.message);
    $('connect-btn').disabled = false;
    $('connect-btn').textContent = 'Connect Instagram Account';
  }
}

// ── Account info ──────────────────────────────────────────
async function loadAccount() {
  try {
    const res = await fetch('/account');
    const data = await res.json();
    if (data.error) {
      $('account-info').innerHTML = '<div class="info-item"><div class="label">Error</div><div class="value" style="color:var(--error)">' + data.error + '</div></div>';
      return;
    }
    const fields = ['username','name','id','biography','followers_count','follows_count','media_count','website'];
    const labels = {username:'Username',name:'Name',id:'ID',biography:'Bio',followers_count:'Followers',follows_count:'Following',media_count:'Posts',website:'Website'};
    let html = '';
    fields.forEach(f => {
      if (data[f] !== undefined) {
        const val = f === 'username' ? '@' + data[f] : data[f];
        html += '<div class="info-item"><div class="label">' + (labels[f]||f) + '</div><div class="value">' + val + '</div></div>';
      }
    });
    $('account-info').innerHTML = html;
  } catch (e) {
    $('account-info').innerHTML = '<div class="info-item"><div class="label">Error</div><div class="value">' + e.message + '</div></div>';
  }
}

async function refreshToken() {
  try {
    const res = await fetch('/auth/refresh', {method:'POST'});
    const data = await res.json();
    if (data.error) alert('Error: ' + data.error);
    else alert('Token refreshed successfully!');
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ── Tabs ──────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  $('tab-' + name).classList.add('active');
}

// ── Media type toggle ─────────────────────────────────────
document.getElementById('pub-media-type').addEventListener('change', function() {
  $('pub-image-group').classList.toggle('hidden', this.value !== 'image');
  $('pub-images-group').classList.toggle('hidden', this.value !== 'carousel');
  $('pub-video-group').classList.toggle('hidden', this.value !== 'reel');
});

// ── Generate type toggle ──────────────────────────────────
$('gen-type').addEventListener('change', function() {
  const labels = {post:'Topic',caption:'Image Description',hashtags:'Content Description',strategy:'Niche',chat:'Message'};
  $('gen-input-label').textContent = labels[this.value] || 'Input';
  $('gen-style-group').classList.toggle('hidden', this.value === 'hashtags' || this.value === 'chat');
});

// ── Generate content ──────────────────────────────────────
async function generateContent() {
  const type = $('gen-type').value;
  const input = $('gen-input').value.trim();
  if (!input) return;
  const btn = $('gen-btn');
  const out = $('gen-output');
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Generating...';
  out.className = 'output'; out.textContent = '';

  let endpoint = '/' + type;
  let body = {};
  if (type === 'post') { body = {topic: input, style: $('gen-style').value, include_hashtags: true}; }
  else if (type === 'caption') { body = {description: input, tone: $('gen-style').value}; }
  else if (type === 'hashtags') { body = {description: input, count: 15}; }
  else if (type === 'strategy') { body = {niche: input, goals: 'growth'}; }
  else if (type === 'chat') { body = {message: input}; }

  try {
    const res = await fetch(endpoint, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(body),
    });
    const data = await res.json();
    out.className = 'output show';
    if (data.error) { out.classList.add('error'); out.textContent = data.error; }
    else {
      out.classList.add('success');
      out.textContent = data.post || data.caption || data.hashtags || data.strategy || data.response || JSON.stringify(data, null, 2);
    }
  } catch (e) {
    out.className = 'output show error'; out.textContent = e.message;
  }
  btn.disabled = false; btn.textContent = 'Generate';
}

// ── Publish ───────────────────────────────────────────────
async function publishContent() {
  const topic = $('pub-topic').value.trim();
  if (!topic) return;
  const btn = $('pub-btn');
  const out = $('pub-output');
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Publishing...';
  out.className = 'output'; out.textContent = '';

  const mediaType = $('pub-media-type').value;
  let body = {
    topic: topic,
    style: $('pub-style').value,
    include_hashtags: true,
    dry_run: $('pub-dry-run').checked,
  };
  if (mediaType === 'image') body.image_url = $('pub-image-url').value.trim();
  else if (mediaType === 'carousel') body.image_urls = $('pub-image-urls').value.split('\\n').map(s=>s.trim()).filter(Boolean);
  else if (mediaType === 'reel') body.video_url = $('pub-video-url').value.trim();

  try {
    const res = await fetch('/publish', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(body),
    });
    const data = await res.json();
    out.className = 'output show';
    if (data.error) { out.classList.add('error'); out.textContent = data.error; }
    else { out.classList.add('success'); out.textContent = JSON.stringify(data, null, 2); }
  } catch (e) {
    out.className = 'output show error'; out.textContent = e.message;
  }
  btn.disabled = false; btn.textContent = 'Publish';
}

// ── Image generation ──────────────────────────────────────
async function generateImage() {
  const prompt = $('img-prompt').value.trim();
  if (!prompt) return;
  const btn = $('img-btn');
  const out = $('img-output');
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Generating Image...';
  out.className = 'output'; out.textContent = '';

  const body = {
    prompt: prompt,
    width: parseInt($('img-width').value) || 1024,
    height: parseInt($('img-height').value) || 1024,
    steps: parseInt($('img-steps').value) || 4,
  };

  try {
    const res = await fetch('/image', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(body),
    });
    const data = await res.json();
    out.className = 'output show';
    if (data.error) { out.classList.add('error'); out.textContent = data.error; }
    else { out.classList.add('success'); out.textContent = 'Image saved to: ' + data.image_path; }
  } catch (e) {
    out.className = 'output show error'; out.textContent = e.message;
  }
  btn.disabled = false; btn.textContent = 'Generate Image';
}

// ── Insights ──────────────────────────────────────────────
async function loadInsights() {
  const out = $('ins-output');
  out.className = 'output'; out.textContent = 'Loading...';
  try {
    const period = $('ins-period').value;
    const res = await fetch('/insights?account=true&period=' + period);
    const data = await res.json();
    out.className = 'output show';
    if (data.error) { out.classList.add('error'); out.textContent = data.error; }
    else { out.classList.add('success'); out.textContent = JSON.stringify(data, null, 2); }
  } catch (e) {
    out.className = 'output show error'; out.textContent = e.message;
  }
}

// ── Init ──────────────────────────────────────────────────
checkStatus();
</script>
</body>
</html>'''


def run_server(port: int = DEFAULT_PORT, host: str = "127.0.0.1", oauth_redirect_uri: Optional[str] = None):
    """Start the HTTP API server.

    Args:
        port: Port to listen on (default: 21420).
        host: Bind address (default: 127.0.0.1).
        oauth_redirect_uri: Override OAuth redirect URI for reverse proxy setups.
    """
    app = create_app(oauth_redirect_uri=oauth_redirect_uri)
    print(f"🚀 Instagram-Agent server starting on http://{host}:{port}")
    if oauth_redirect_uri:
        print(f"   OAuth redirect URI: {oauth_redirect_uri}")
    print(f"   Endpoints: /chat, /post, /caption, /hashtags, /strategy, /publish, /image, /account, /insights")
    print(f"   OAuth: /auth/url, /auth/callback, /auth/refresh")
    app.run(host=host, port=port)
