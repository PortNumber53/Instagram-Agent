"""Allow running as: python -m instagram_agent"""

from instagram_agent.cli import main

if __name__ == "__main__":
    raise SystemExit(main() or 0)
