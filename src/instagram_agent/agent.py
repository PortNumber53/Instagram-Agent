"""Core agent module — connects to NVIDIA NIM API with streaming and reasoning."""

import json
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure the package root (src/) is on sys.path so relative imports work
# when running this file directly: python src/instagram_agent/agent.py
_src_dir = str(Path(__file__).resolve().parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from openai import OpenAI

from instagram_agent.config import get_nvidia_api_key

# Default NVIDIA NIM model
DEFAULT_MODEL = "z-ai/glm-5.1"

# NVIDIA NIM base URL
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"


class InstagramAgent:
    """An AI agent that generates Instagram content using NVIDIA NIM.

    Supports streaming output with optional chain-of-thought reasoning.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        self.api_key = api_key or get_nvidia_api_key()
        self.model = model or DEFAULT_MODEL
        self.system_prompt = system_prompt or self._default_system_prompt()

        self.client = OpenAI(
            base_url=NIM_BASE_URL,
            api_key=self.api_key,
        )

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "You are an expert Instagram content creator and social media strategist. "
            "You help users create engaging Instagram posts, captions, hashtags, "
            "and content strategies. You understand Instagram's algorithm, best posting "
            "times, trending formats, and audience engagement techniques.\n\n"
            "When creating content, always consider:\n"
            "- Visual storytelling and aesthetic consistency\n"
            "- Engaging hooks in the first line\n"
            "- Strategic hashtag usage (mix of broad and niche)\n"
            "- Call-to-action that drives engagement\n"
            "- Current Instagram trends and format best practices\n"
            "- Character limits and formatting for readability\n"
        )

    def chat(
        self,
        message: str,
        stream: bool = True,
        show_reasoning: bool = False,
    ) -> str:
        """Send a message and get a response, with optional streaming + reasoning.

        Args:
            message: The user prompt / question.
            stream: If True, tokens are printed as they arrive.
            show_reasoning: If True, include chain-of-thought reasoning before answer.

        Returns:
            The full assistant response text.
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]

        if show_reasoning:
            messages.append({
                "role": "system",
                "content": (
                    "Before answering, think through the problem step by step "
                    "inside <reasoning>...</reasoning> tags. "
                    "Then provide your answer after the closing tag."
                ),
            })

        messages.append({"role": "user", "content": message})

        if stream:
            return self._stream_chat(messages, show_reasoning)
        else:
            return self._sync_chat(messages)

    def _stream_chat(self, messages: list, show_reasoning: bool) -> str:
        """Stream the response token-by-token to stdout."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            temperature=0.7,
            max_tokens=2048,
        )

        full_response = []
        in_reasoning = False

        for chunk in response:
            # Some models emit chunks with empty choices (e.g. usage chunks,
            # role-only chunks at stream start). Guard against IndexError.
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # delta.content may be None on role-only or finish_reason chunks
            content = getattr(delta, "content", None)
            if not content:
                continue

            token = content

            # Track reasoning tags for display
            if show_reasoning:
                if "<reasoning>" in token:
                    in_reasoning = True
                    token = token.replace("<reasoning>", "")
                    print("\n🧠 Reasoning:\n" + "─" * 40, file=sys.stderr)
                if "</reasoning>" in token:
                    in_reasoning = False
                    token = token.replace("</reasoning>", "")
                    print(token, end="", file=sys.stderr)
                    print("\n" + "─" * 40 + "\n\n💡 Answer:\n", file=sys.stderr)
                    continue

            if in_reasoning:
                print(token, end="", file=sys.stderr)
            else:
                print(token, end="", flush=True)

            full_response.append(token)

        print()  # final newline
        return "".join(full_response)

    def _sync_chat(self, messages: list) -> str:
        """Non-streaming request — returns the full response at once."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=False,
            temperature=0.7,
            max_tokens=2048,
        )
        return response.choices[0].message.content

    def generate_post(
        self,
        topic: str,
        style: str = "professional",
        include_hashtags: bool = True,
        show_reasoning: bool = False,
    ) -> str:
        """Generate an Instagram post about a topic.

        Args:
            topic: What the post should be about.
            style: Content style — professional, casual, funny, inspirational, etc.
            include_hashtags: Whether to include hashtag suggestions.
            show_reasoning: Show the AI's reasoning process.

        Returns:
            Generated post content.
        """
        prompt = (
            f"Create an Instagram post about: {topic}\n"
            f"Style: {style}\n"
        )
        if include_hashtags:
            prompt += "Include 10-15 relevant hashtags.\n"
        prompt += "Format the caption with line breaks for readability."

        return self.chat(prompt, stream=True, show_reasoning=show_reasoning)

    def generate_caption(
        self,
        image_description: str,
        tone: str = "engaging",
        show_reasoning: bool = False,
    ) -> str:
        """Generate a caption for an image.

        Args:
            image_description: Description of the image content.
            tone: Desired tone — engaging, witty, minimal, etc.
            show_reasoning: Show the AI's reasoning process.

        Returns:
            Generated caption.
        """
        prompt = (
            f"Write an Instagram caption for an image described as:\n"
            f"{image_description}\n\n"
            f"Tone: {tone}\n"
            f"Keep it concise but compelling. Include a call-to-action."
        )

        return self.chat(prompt, stream=True, show_reasoning=show_reasoning)

    def generate_hashtags(
        self,
        content_description: str,
        count: int = 15,
        show_reasoning: bool = False,
    ) -> str:
        """Generate hashtags for content.

        Args:
            content_description: Description of the content.
            count: Number of hashtags to generate.
            show_reasoning: Show the AI's reasoning process.

        Returns:
            Generated hashtags.
        """
        prompt = (
            f"Generate {count} strategic hashtags for Instagram content about:\n"
            f"{content_description}\n\n"
            f"Mix broad/popular and niche hashtags. "
            f"Format as a single line: #tag1 #tag2 #tag3 ..."
        )

        return self.chat(prompt, stream=True, show_reasoning=show_reasoning)

    def content_strategy(
        self,
        niche: str,
        goals: str = "growth",
        show_reasoning: bool = False,
    ) -> str:
        """Generate a content strategy.

        Args:
            niche: The Instagram niche (e.g., 'fitness', 'tech', 'food').
            goals: Primary goals — growth, engagement, brand-awareness, etc.
            show_reasoning: Show the AI's reasoning process.

        Returns:
            Content strategy recommendations.
        """
        prompt = (
            f"Create an Instagram content strategy for the '{niche}' niche.\n"
            f"Primary goal: {goals}\n\n"
            f"Include:\n"
            f"- Content pillars (4-5 themes)\n"
            f"- Posting frequency recommendation\n"
            f"- Best times to post\n"
            f"- Content format recommendations (Reels, Stories, Carousels, etc.)\n"
            f"- Growth tactics specific to this niche"
        )

        return self.chat(prompt, stream=True, show_reasoning=show_reasoning)
