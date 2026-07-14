"""CLI entry point for Instagram-Agent."""

import argparse
import json
import sys
from pathlib import Path

# Ensure the package root (src/) is on sys.path so relative imports work
# when running this file directly: python src/instagram_agent/cli.py
_src_dir = str(Path(__file__).resolve().parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from instagram_agent.agent import InstagramAgent, DEFAULT_MODEL
from instagram_agent.config import CONFIG_FILE


def main():
    parser = argparse.ArgumentParser(
        prog="instagram-agent",
        description="Instagram content agent powered by FreeLLMAPI with direct publishing",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── chat (default interactive) ──
    chat_parser = subparsers.add_parser("chat", help="Chat with the Instagram agent")
    chat_parser.add_argument("message", nargs="*", help="Message to send (interactive if omitted)")
    chat_parser.add_argument("--no-stream", action="store_true", help="Disable streaming")
    chat_parser.add_argument("--reasoning", action="store_true", help="Show reasoning process")

    # ── generate post ──
    post_parser = subparsers.add_parser("post", help="Generate an Instagram post")
    post_parser.add_argument("topic", help="Topic of the post")
    post_parser.add_argument("--style", default="professional", help="Style: professional, casual, funny, etc.")
    post_parser.add_argument("--no-hashtags", action="store_true", help="Skip hashtags")
    post_parser.add_argument("--reasoning", action="store_true", help="Show reasoning process")

    # ── generate caption ──
    caption_parser = subparsers.add_parser("caption", help="Generate a caption for an image")
    caption_parser.add_argument("description", help="Image description")
    caption_parser.add_argument("--tone", default="engaging", help="Tone: engaging, witty, minimal, etc.")
    caption_parser.add_argument("--reasoning", action="store_true", help="Show reasoning process")

    # ── generate hashtags ──
    hashtag_parser = subparsers.add_parser("hashtags", help="Generate hashtags")
    hashtag_parser.add_argument("description", help="Content description")
    hashtag_parser.add_argument("--count", type=int, default=15, help="Number of hashtags")
    hashtag_parser.add_argument("--reasoning", action="store_true", help="Show reasoning process")

    # ── content strategy ──
    strategy_parser = subparsers.add_parser("strategy", help="Generate content strategy")
    strategy_parser.add_argument("niche", help="Instagram niche (e.g., fitness, tech, food)")
    strategy_parser.add_argument("--goals", default="growth", help="Primary goals")
    strategy_parser.add_argument("--reasoning", action="store_true", help="Show reasoning process")

    # ── auth (OAuth flow) ──
    auth_parser = subparsers.add_parser("auth", help="Run Instagram/Facebook OAuth flow to get access token")
    auth_parser.add_argument(
        "--port", type=int, default=8765,
        help="Local port for OAuth callback (default: 8765)",
    )
    auth_parser.add_argument(
        "--no-browser", action="store_true",
        help="Don't auto-open the browser; print the URL instead",
    )
    auth_parser.add_argument(
        "--refresh", action="store_true",
        help="Refresh the current long-lived token instead of full OAuth",
    )

    # ── publish (generate + post) ──
    publish_parser = subparsers.add_parser("publish", help="Generate AI content and publish to Instagram")
    publish_parser.add_argument("topic", help="Topic for the AI-generated caption")
    publish_parser.add_argument(
        "--image", dest="image_url",
        help="Publicly accessible URL of the image to post",
    )
    publish_parser.add_argument(
        "--images", dest="image_urls", nargs="+",
        help="URLs for a carousel post (2-10 images)",
    )
    publish_parser.add_argument(
        "--video", dest="video_url",
        help="Publicly accessible URL of the video for a Reel",
    )
    publish_parser.add_argument("--style", default="professional", help="Caption style")
    publish_parser.add_argument("--no-hashtags", action="store_true", help="Skip hashtags in caption")
    publish_parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate the caption but do NOT publish to Instagram",
    )
    publish_parser.add_argument("--reasoning", action="store_true", help="Show AI reasoning process")

    # ── insights ──
    insights_parser = subparsers.add_parser("insights", help="Get insights for a published post or your account")
    insights_parser.add_argument("--media-id", help="Media ID to get insights for")
    insights_parser.add_argument("--account", action="store_true", help="Get account-level insights")
    insights_parser.add_argument("--period", default="day", help="Period for account insights: day, week, days_28")

    # ── account ──
    account_parser = subparsers.add_parser("account", help="Show Instagram account info")

    # ── generate image ──
    image_parser = subparsers.add_parser("image", help="Generate an image from a text prompt")
    image_parser.add_argument("prompt", help="Text prompt for image generation")
    image_parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    image_parser.add_argument("--steps", type=int, default=4, help="Number of inference steps (default: 4)")
    image_parser.add_argument("--height", type=int, default=1024, help="Height of the image in pixels (default: 1024)")
    image_parser.add_argument("--width", type=int, default=1024, help="Width of the image in pixels (default: 1024)")
    image_parser.add_argument("--guidance", type=float, default=4.0, help="Guidance scale (default: 4.0)")
    image_parser.add_argument("--output-dir", type=str, default=None, help="Directory to save the image (default: current directory)")
    image_parser.add_argument("--filename", type=str, default=None, help="Filename for the saved image (default: auto-generated)")
    image_parser.add_argument("--reasoning", action="store_true", help="Show reasoning process")

    # ── global options ──
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"LLM model (default: {DEFAULT_MODEL})")
    parser.add_argument("--api-key", default=None, help="LLM API key (overrides config/env)")
    parser.add_argument("--reasoning", action="store_true", help="Show reasoning (global flag)")

    args = parser.parse_args()

    # Apply global reasoning flag if set
    show_reasoning = getattr(args, "reasoning", False)

    # ── Commands that don't need the AI agent ──
    if args.command == "auth":
        return _cmd_auth(args)

    if args.command == "account":
        return _cmd_account()

    if args.command == "insights":
        return _cmd_insights(args)

    # ── Commands that need the AI agent ──
    try:
        agent = InstagramAgent(
            model=args.model,
            api_key=args.api_key if args.api_key else None,
        )
    except SystemExit:
        return 1

    # ── Dispatch commands ──
    if args.command == "chat":
        msg = " ".join(args.message) if args.message else None
        if msg:
            agent.chat(msg, stream=not args.no_stream, show_reasoning=show_reasoning)
        else:
            interactive_chat(agent, show_reasoning=show_reasoning)

    elif args.command == "post":
        agent.generate_post(
            topic=args.topic,
            style=args.style,
            include_hashtags=not args.no_hashtags,
            show_reasoning=show_reasoning,
        )

    elif args.command == "caption":
        agent.generate_caption(
            image_description=args.description,
            tone=args.tone,
            show_reasoning=show_reasoning,
        )

    elif args.command == "hashtags":
        agent.generate_hashtags(
            content_description=args.description,
            count=args.count,
            show_reasoning=show_reasoning,
        )

    elif args.command == "strategy":
        agent.content_strategy(
            niche=args.niche,
            goals=args.goals,
            show_reasoning=show_reasoning,
        )

    elif args.command == "publish":
        return _cmd_publish(agent, args, show_reasoning)

    elif args.command == "image":
        agent.generate_image(
            prompt=args.prompt,
            seed=args.seed,
            num_inference_steps=args.steps,
            height=args.height,
            width=args.width,
            guidance=args.guidance,
            output_dir=args.output_dir,
            filename=args.filename,
            show_reasoning=show_reasoning,
        )

    else:
        # No subcommand → print help
        parser.print_help()
        print("\nTip: Use 'instagram-agent auth' to set up OAuth, 'instagram-agent publish' to post to Instagram.")
        return 0

    return 0


# ── Subcommand implementations ──────────────────────────────────


def _cmd_auth(args) -> int:
    """Handle the 'auth' subcommand — OAuth flow or token refresh."""
    from instagram_agent.oauth import start_oauth_flow, refresh_long_lived_token

    if args.refresh:
        try:
            refresh_long_lived_token()
            return 0
        except SystemExit as e:
            print(f"Token refresh failed: {e}", file=sys.stderr)
            return 1

    try:
        result = start_oauth_flow(
            port=args.port,
            open_browser=not args.no_browser,
        )
        print("✅ OAuth complete! You can now use 'instagram-agent publish'.")
        return 0
    except SystemExit as e:
        print(f"OAuth failed: {e}", file=sys.stderr)
        return 1


def _cmd_account() -> int:
    """Handle the 'account' subcommand — show Instagram account info."""
    from instagram_agent.instagram import InstagramClient

    try:
        client = InstagramClient()
        info = client.get_account_info()

        print("\n📸 Instagram Account Info")
        print("=" * 40)
        print(f"  Username:  @{info.get('username', 'N/A')}")
        print(f"  Name:      {info.get('name', 'N/A')}")
        print(f"  ID:        {info.get('id', 'N/A')}")
        print(f"  Bio:       {info.get('biography', 'N/A')}")
        print(f"  Followers: {info.get('followers_count', 'N/A')}")
        print(f"  Following: {info.get('follows_count', 'N/A')}")
        print(f"  Posts:     {info.get('media_count', 'N/A')}")
        print(f"  Website:   {info.get('website', 'N/A')}")
        print()

        return 0
    except SystemExit as e:
        print(f"Failed to get account info: {e}", file=sys.stderr)
        return 1


def _cmd_insights(args) -> int:
    """Handle the 'insights' subcommand — media or account insights."""
    from instagram_agent.instagram import InstagramClient

    try:
        client = InstagramClient()

        if args.media_id:
            insights = client.get_media_insights(args.media_id)
            print(f"\n📊 Insights for media {args.media_id}")
            print("=" * 40)
            for name, value in insights.items():
                print(f"  {name}: {value}")
            print()
        elif args.account:
            insights = client.get_account_insights(period=args.period)
            print(f"\n📊 Account Insights (period: {args.period})")
            print("=" * 40)
            for name, value in insights.items():
                print(f"  {name}: {value}")
            print()
        else:
            print("ERROR: Specify --media-id <id> or --account for insights.", file=sys.stderr)
            return 1

        return 0
    except SystemExit as e:
        print(f"Failed to get insights: {e}", file=sys.stderr)
        return 1


def _cmd_publish(agent: InstagramAgent, args, show_reasoning: bool) -> int:
    """Handle the 'publish' subcommand — generate content and post to Instagram."""
    # Determine post type
    media_type = None
    if args.video_url:
        media_type = "reel"
    elif args.image_urls and len(args.image_urls) > 1:
        media_type = "carousel"
    elif args.image_url:
        media_type = "image"

    if not media_type:
        print(
            "ERROR: Specify a media URL for publishing.\n"
            "  --image <url>       Single image post\n"
            "  --images <url> ...  Carousel post (2-10 images)\n"
            "  --video <url>       Reel video post",
            file=sys.stderr,
        )
        return 1

    try:
        if media_type == "image":
            result = agent.publish_post(
                image_url=args.image_url,
                topic=args.topic,
                style=args.style,
                include_hashtags=not args.no_hashtags,
                dry_run=args.dry_run,
                show_reasoning=show_reasoning,
            )
        elif media_type == "carousel":
            result = agent.publish_carousel(
                image_urls=args.image_urls,
                topic=args.topic,
                style=args.style,
                include_hashtags=not args.no_hashtags,
                dry_run=args.dry_run,
                show_reasoning=show_reasoning,
            )
        elif media_type == "reel":
            result = agent.publish_reel(
                video_url=args.video_url,
                topic=args.topic,
                style=args.style,
                include_hashtags=not args.no_hashtags,
                dry_run=args.dry_run,
                show_reasoning=show_reasoning,
            )

        # Print summary
        print(f"\n📋 Result:")
        print(f"  Dry run:  {result['dry_run']}")
        print(f"  Caption:  {result['caption'][:80]}..." if len(result['caption']) > 80 else f"  Caption:  {result['caption']}")
        if not result['dry_run']:
            print(f"  Container: {result.get('container_id', 'N/A')}")
            print(f"  Media ID:  {result.get('media_id', 'N/A')}")
        print()

        return 0
    except SystemExit as e:
        print(f"Publish failed: {e}", file=sys.stderr)
        return 1


def interactive_chat(agent: InstagramAgent, show_reasoning: bool = False):
    """Run an interactive chat loop."""
    print("📷 Instagram-Agent Interactive Chat")
    print(f" Model: {agent.model}")
    print(f" Type 'quit' or Ctrl+C to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye! 👋")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye! 👋")
            break

        print("\nAgent: ", end="", flush=True)
        agent.chat(user_input, stream=True, show_reasoning=show_reasoning)
        print()


if __name__ == "__main__":
    sys.exit(main() or 0)
