"""Image generation wrapper using MFlux (MLX-native Flux models)."""

import os
import time
from pathlib import Path
from typing import Optional

import mlx.core as mx
from mflux.models.flux.variants.txt2img.flux import Flux1
from mflux.models.common.config.model_config import ModelConfig
from mflux.utils.generated_image import GeneratedImage


class MFluxGenerator:
    """Generate images locally using MFlux (Apple Silicon MLX).

    Wraps the mflux library to provide a simple interface for text-to-image
    generation using FLUX.1 models (schnell / dev).
    """

    def __init__(
        self,
        model_config: ModelConfig = ModelConfig.schnell(),
    ):
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
        """Generate an image from a text prompt and save it to disk.

        Args:
            prompt: Text description of the image to generate.
            seed: Random seed for reproducibility. If None, a random seed is used.
            num_inference_steps: Number of denoising steps.
            height: Image height in pixels.
            width: Image width in pixels.
            guidance: Guidance scale (used by dev model; schnell ignores it).
            output_dir: Directory to save the image. Defaults to current directory.
            filename: Output filename. If None, auto-generated from timestamp.

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