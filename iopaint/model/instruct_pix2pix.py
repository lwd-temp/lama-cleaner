import PIL.Image
import cv2
import torch
from loguru import logger

from iopaint.const import INSTRUCT_PIX2PIX_NAME
from iopaint.model.base import DiffusionInpaintModel
from iopaint.schema import InpaintRequest


class InstructPix2Pix(DiffusionInpaintModel):
    name = INSTRUCT_PIX2PIX_NAME
    pad_mod = 8
    min_size = 512

    def init_model(self, device: torch.device, **kwargs):
        from diffusers import StableDiffusionInstructPix2PixPipeline

        fp16 = not kwargs.get("no_half", False)

        model_kwargs = {}
        if kwargs["disable_nsfw"] or kwargs.get("cpu_offload", False):
            logger.info("Disable Stable Diffusion Model NSFW checker")
            model_kwargs.update(
                dict(
                    safety_checker=None,
                    feature_extractor=None,
                    requires_safety_checker=False,
                )
            )

        use_gpu = device == torch.device("cuda") and torch.cuda.is_available()
        torch_dtype = torch.float16 if use_gpu and fp16 else torch.float32
        self.model = StableDiffusionInstructPix2PixPipeline.from_pretrained(
            self.name, variant="fp16", torch_dtype=torch_dtype, **model_kwargs
        )

        if kwargs.get("cpu_offload", False) and use_gpu:
            logger.info("Enable sequential cpu offload")
            self.model.enable_sequential_cpu_offload(gpu_id=0)
        else:
            self.model = self.model.to(device)

    def forward(self, image, mask, config: InpaintRequest):
        """Input image and output image have same size
        image: [H, W, C] RGB
        mask: [H, W, 1] 255 means area to repaint
        return: BGR IMAGE
        edit = pipe(prompt, image=image, num_inference_steps=20, image_guidance_scale=1.5, guidance_scale=7).images[0]
        """
        output = self.model(
            image=PIL.Image.fromarray(image),
            prompt=config.prompt,
            negative_prompt=config.negative_prompt,
            num_inference_steps=config.sd_steps,
            image_guidance_scale=config.p2p_image_guidance_scale,
            guidance_scale=config.sd_guidance_scale,
            output_type="np",
            generator=torch.manual_seed(config.sd_seed),
        ).images[0]

        output = (output * 255).round().astype("uint8")
        output = cv2.cvtColor(output, cv2.COLOR_RGB2BGR)
        return output
