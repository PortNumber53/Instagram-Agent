"""Image generation wrapper using MFlux (MLX-native Flux models)."""

import os
import time
from typing import Optional

from mflux.models.flux.variants.txt2img.flux import Flux1


class MFluxGenerator:
    """Generate images locally using MFlux (Apple Silicon MLX).

    Wraps the mflux library to provide a simple interface for text-to-image
    generation using FLUX.1 models (schnell / dev).
    """

    def __init__(
        self,
        model_name: str = "schnell",
        quantize: int = 8,
    ):
        self.model_name = model_name
        self.quantize = quantize
        self._flux: Optional[Flux1] = None

    def _get_flux(self) -> Flux1:
        if self._flux is None:
            from instagram_agent.config import get
            hf_token = get("HF_TOKEN") or get("HUGGING_FACE_HUB_TOKEN")
            if hf_token:
                os.environ["HF_TOKEN"] = hf_token
            os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
            print(f"Loading FLUX model '{self.model_name}' (quantize={self.quantize})...")
            self._flux = Flux1.from_name(
                model_name=self.model_name,
                quantize=self.quantize,
            )
        return self._flux

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
    ) -> str:
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
            seed = int(time.time()) % (2**32)

        flux = self._get_flux()

        kwargs = dict(
            seed=seed,
            prompt=prompt,
            num_inference_steps=num_inference_steps,
            height=height,
            width=width,
        )

        if self.model_name != "schnell":
            kwargs["guidance"] = guidance

        image = flux.generate_image(**kwargs)

        if filename is None:
            filename = f"flux_{seed}_{int(time.time())}.png"
        if not filename.endswith(".png"):
            filename += ".png"

        save_dir = output_dir or os.getcwd()
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)

        image.save(path=save_path)

        return save_path
