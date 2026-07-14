"""Core agent module — connects to FreeLLMAPI with streaming and reasoning.

Also provides Instagram publishing via the Facebook Graph API.
"""

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

from instagram_agent.config import get_llm_api_key, get_llm_base_url, get_llm_model, get_ig_access_token, get_ig_account_id
from instagram_agent.image_gen.mflux_generator import MFluxGenerator

# Default model — 'auto' lets FreeLLMAPI pick the best available model
DEFAULT_MODEL = "auto"

# Default base URL for FreeLLMAPI
DEFAULT_BASE_URL = "http://localhost:3001/v1"


class InstagramAgent:
    """An AI agent that generates Instagram content using FreeLLMAPI.

    Supports streaming output with optional chain-of-thought reasoning,
    and publishing directly to Instagram via the Facebook Graph API.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        self.api_key = api_key or get_llm_api_key()
        self.model = model or get_llm_model() or DEFAULT_MODEL
        self.base_url = base_url or get_llm_base_url() or DEFAULT_BASE_URL
        self.system_prompt = system_prompt or self._default_system_prompt()

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )
        
        # Initialize image generator
        self.image_generator = MFluxGenerator()

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
        stream: bool = True,
    ) -> str:
        """Generate an Instagram post about a topic.

        Args:
            topic: What the post should be about.
            style: Content style — professional, casual, funny, inspirational, etc.
            include_hashtags: Whether to include hashtag suggestions.
            show_reasoning: Show the AI's reasoning process.
            stream: If True, stream output to stdout.

        Returns:
            Generated post content.
        """
        prompt = (
            f"Create an Instagram post about: {topic}\n"
            f"Style: {style}\n"
        )
        if include_hashtags:
            prompt += "Include 10-15 relevant hashtags.\n"
        prompt += (
            "Format the caption with line breaks for readability.\n"
            "IMPORTANT: Return ONLY the caption text, no extra commentary."
        )

        return self.chat(prompt, stream=stream, show_reasoning=show_reasoning)

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

    # ──────────────────────────────────────────────────────────────────
    # Instagram publishing via Facebook Graph API
    # ──────────────────────────────────────────────────────────────────

    def publish_post(
        self,
        image_url: str,
        topic: str,
        style: str = "professional",
        include_hashtags: bool = True,
        dry_run: bool = False,
        show_reasoning: bool = False,
    ) -> dict:
        """Generate AI content for a topic, then publish it to Instagram.

        This combines content generation with API publishing:
        1. Generate a caption using AI
        2. Create a media container on Instagram
        3. Wait for processing
        4. Publish the container

        Args:
            image_url: Publicly accessible URL of the image to post.
            topic: What the post should be about (drives AI caption generation).
            style: Content style — professional, casual, funny, etc.
            include_hashtags: Whether to include hashtags in the caption.
            dry_run: If True, generate the caption but do NOT publish.
            show_reasoning: Show the AI's reasoning process.

        Returns:
            dict with keys:
            - caption: The generated caption text
            - container_id: Media container ID (None if dry_run)
            - media_id: Published media ID (None if dry_run or not yet published)
            - dry_run: Whether this was a dry run
        """
        from instagram_agent.instagram import InstagramClient

        # 1. Generate the caption (non-streaming so we capture the full text)
        print("📝 Generating caption...")
        caption = self.generate_post(
            topic=topic,
            style=style,
            include_hashtags=include_hashtags,
            show_reasoning=show_reasoning,
            stream=False,
        )

        # Clean up any surrounding quotes the model might add
        caption = caption.strip().strip('"').strip("'")

        print(f"\n{'='*50}")
        print(f"Generated caption:\n{caption}")
        print(f"{'='*50}\n")

        if dry_run:
            print("🏁 Dry run — skipping publish.")
            return {
                "caption": caption,
                "container_id": None,
                "media_id": None,
                "dry_run": True,
            }

        # 2. Create the Instagram client and publish
        print("📤 Publishing to Instagram...")
        client = InstagramClient()

        container_id = client.create_image_container(
            image_url=image_url,
            caption=caption,
        )

        client.wait_for_container(container_id)

        result = client.publish_media(container_id)

        return {
            "caption": caption,
            "container_id": container_id,
            "media_id": result.get("id"),
            "dry_run": False,
        }

    def publish_carousel(
        self,
        image_urls: list[str],
        topic: str,
        style: str = "professional",
        include_hashtags: bool = True,
        dry_run: bool = False,
        show_reasoning: bool = False,
    ) -> dict:
        """Generate AI content then publish a carousel post to Instagram.

        Args:
            image_urls: List of publicly accessible image URLs (2-10 images).
            topic: What the post should be about.
            style: Content style.
            include_hashtags: Whether to include hashtags.
            dry_run: If True, generate the caption but do NOT publish.
            show_reasoning: Show the AI's reasoning process.

        Returns:
            dict with caption, container_id, media_id, dry_run.
        """
        from instagram_agent.instagram import InstagramClient

        print("📝 Generating caption...")
        caption = self.generate_post(
            topic=topic,
            style=style,
            include_hashtags=include_hashtags,
            show_reasoning=show_reasoning,
            stream=False,
        )
        caption = caption.strip().strip('"').strip("'")

        print(f"\n{'='*50}")
        print(f"Generated caption:\n{caption}")
        print(f"{'='*50}\n")

        if dry_run:
            print("🏁 Dry run — skipping publish.")
            return {
                "caption": caption,
                "container_id": None,
                "media_id": None,
                "dry_run": True,
            }

        print("📤 Publishing carousel to Instagram...")
        client = InstagramClient()

        container_id = client.create_carousel_container(
            image_urls=image_urls,
            caption=caption,
        )

        client.wait_for_container(container_id)
        result = client.publish_media(container_id)

        return {
            "caption": caption,
            "container_id": container_id,
            "media_id": result.get("id"),
            "dry_run": False,
        }

    def publish_reel(
        self,
        video_url: str,
        topic: str,
        style: str = "professional",
        include_hashtags: bool = True,
        dry_run: bool = False,
        show_reasoning: bool = False,
    ) -> dict:
        """Generate AI content then publish a Reel to Instagram.

        Args:
            video_url: Publicly accessible URL of the video (MP4, 3-90s).
            topic: What the reel should be about.
            style: Content style.
            include_hashtags: Whether to include hashtags.
            dry_run: If True, generate the caption but do NOT publish.
            show_reasoning: Show the AI's reasoning process.

        Returns:
            dict with caption, container_id, media_id, dry_run.
        """
        from instagram_agent.instagram import InstagramClient

        print("📝 Generating caption...")
        caption = self.generate_post(
            topic=topic,
            style=style,
            include_hashtags=include_hashtags,
            show_reasoning=show_reasoning,
            stream=False,
        )
        caption = caption.strip().strip('"').strip("'")

        print(f"\n{'='*50}")
        print(f"Generated caption:\n{caption}")
        print(f"{'='*50}\n")

        if dry_run:
            print("🏁 Dry run — skipping publish.")
            return {
                "caption": caption,
                "container_id": None,
                "media_id": None,
                "dry_run": True,
            }

        print("📤 Publishing Reel to Instagram...")
        client = InstagramClient()

        container_id = client.create_reel_container(
            video_url=video_url,
            caption=caption,
        )

        client.wait_for_container(container_id, timeout=600)  # Videos take longer
        result = client.publish_media(container_id)

        return {
            "caption": caption,
            "container_id": container_id,
            "media_id": result.get("id"),
            "dry_run": False,
        }

    def generate_image(
        self,
        prompt: str,
        seed: Optional[int] = None,
        num_inference_steps: int = 4,
        height: int = 1024,
        width: int = 1024,
        guidance: float = 4.0,
        output_dir: Optional[str] = None,
        filename: Optional[str] = None,
        show_reasoning: bool = False,
    ) -> str:
        """Generate an image from a text prompt using MFlux.

        Args:
            prompt: The text prompt to generate the image from.
            seed: Random seed for reproducibility. If None, a random seed is used.
            num_inference_steps: Number of denoising steps (default: 4 for schnell).
            height: Height of the generated image in pixels (default: 1024).
            width: Width of the generated image in pixels (default: 1024).
            guidance: Guidance scale for generation (default: 4.0).
            output_dir: Directory to save the image. If None, uses current directory.
            filename: Filename for the saved image. If None, a name is generated.
            show_reasoning: Show the reasoning process for image generation.

        Returns:
            Path to the saved image file as a string.
        """
        if show_reasoning:
            print(f"🎨 Generating image with prompt: {prompt}")
            print(f"   Seed: {seed or 'random'}")
            print(f"   Steps: {num_inference_steps}")
            print(f"   Size: {width}x{height}")

        image_path = self.image_generator.generate_image(
            prompt=prompt,
            seed=seed,
            num_inference_steps=num_inference_steps,
            height=height,
            width=width,
            guidance=guidance,
            output_dir=output_dir,
            filename=filename,
        )

        if show_reasoning:
            print(f"✅ Image saved to: {image_path}")

        return str(image_path)
