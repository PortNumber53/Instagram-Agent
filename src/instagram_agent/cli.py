"""CLI entry point for Instagram-Agent."""

import argparse
import sys
from pathlib import Path

# Ensure the package root (src/) is on sys.path so relative imports work
# when running this file directly: python src/instagram_agent/cli.py
_src_dir = str(Path(__file__).resolve().parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from instagram_agent.agent import InstagramAgent, DEFAULT_MODEL
from instagram_agent.config import get_nvidia_api_key, CONFIG_FILE


def main():
    parser = argparse.ArgumentParser(
        prog="instagram-agent",
        description="Instagram content agent powered by NVIDIA NIM",
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

    # ── global options ──
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"NIM model (default: {DEFAULT_MODEL})")
    parser.add_argument("--api-key", default=None, help="NVIDIA API key (overrides config/env)")
    parser.add_argument("--reasoning", action="store_true", help="Show reasoning (global flag)")

    args = parser.parse_args()

    # Apply global reasoning flag if set
    show_reasoning = getattr(args, "reasoning", False)

    # Initialize agent
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

    else:
        # No subcommand → interactive chat
        parser.print_help()
        print("\nTip: Use 'instagram-agent chat' for interactive mode, or one of the subcommands above.")
        return 0

    return 0


def interactive_chat(agent: InstagramAgent, show_reasoning: bool = False):
    """Run an interactive chat loop."""
    print("📸 Instagram-Agent Interactive Chat")
    print(f"   Model: {agent.model}")
    print(f"   Type 'quit' or Ctrl+C to exit.\n")

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
