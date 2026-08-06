"""MFlux image generator for Instagram-Agent."""

import os
from pathlib import Path
from typing import Optional

import mlx.core as mx
from mflux.models.flux.variants.txt2img.flux import Flux1
from mflux.models.common.config.model_config import ModelConfig
from mflux.utils.generated_image import GeneratedImage


class MFluxGenerator:
    """A wrapper around mflux for generating images."""

    def __init__(self, model_config: ModelConfig = ModelConfig.schnell()):
        """Initialize the MFluxGenerator with a specific model config.

        Args:
            model_config: The model configuration to use (default: schnell).
        """
        self.model_config = model_config
        self.flux = Flux1(model_config=model_config)

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
    ) -> Path:
        """Generate an image from a text prompt.

        Args:
            prompt: The text prompt to generate the image from.
            seed: Random seed for reproducibility. If None, a random seed is used.
            num_inference_steps: Number of denoising steps (default: 4 for schnell).
            height: Height of the generated image in pixels (default: 1024).
            width: Width of the generated image in pixels (default: 1024).
            guidance: Guidance scale for generation (default: 4.0).
            output_dir: Directory to save the image. If None, uses current directory.
            filename: Filename for the saved image. If None, a name is generated.

        Returns:
            Path to the saved image file.
        """
        if seed is None:
            seed = mx.random.randint(0, 2**32 - 1).item()

        # Set output directory
        if output_dir is None:
            output_dir = os.getcwd()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate filename if not provided
        if filename is None:
            filename = f"mflux_{seed}_{abs(hash(prompt)) % 10000:04d}.png"
        elif not filename.endswith('.png'):
            filename = filename + '.png'

        full_path = output_path / filename

        # Generate the image
        generated_image: GeneratedImage = self.flux.generate_image(
            seed=seed,
            prompt=prompt,
            num_inference_steps=num_inference_steps,
            height=height,
            width=width,
            guidance=guidance,
        )

        # Save the image
        generated_image.image.save(full_path)

        return full_path