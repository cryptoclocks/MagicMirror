"""Isolated MPS image inpainting worker. JSON lines on stdin/stdout; no camera/network."""
import base64
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / '.local-ai/model'


def emit(**data):
    print(json.dumps(data), flush=True)


def main():
    import torch
    from PIL import Image, ImageFilter
    from diffusers import StableDiffusionInpaintPipeline, LCMScheduler
    if not torch.backends.mps.is_available():
        emit(kind='error', message='ต้องใช้ Apple Metal / MPS'); return
    emit(kind='loading')
    pipe = StableDiffusionInpaintPipeline.from_pretrained(
        str(MODEL), torch_dtype=torch.float16, variant='fp16',
        use_safetensors=True, local_files_only=True)
    pipe.load_lora_weights(str(ROOT/'.local-ai/lcm'),weight_name='pytorch_lora_weights.safetensors',local_files_only=True)
    pipe.fuse_lora();pipe.unload_lora_weights()
    pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)
    pipe.to('mps')
    pipe.enable_attention_slicing('auto')
    for module in pipe.unet.modules():
        if hasattr(module,'upcast_attention'):
            module.upcast_attention=True
            module.upcast_softmax=True
    pipe.enable_vae_slicing()
    pipe.set_progress_bar_config(disable=True)
    emit(kind='ready')
    for line in sys.stdin:
        request = json.loads(line)
        job = request['id']
        try:
            started = time.monotonic()
            image = Image.open(io.BytesIO(base64.b64decode(request['image']))).convert('RGB')
            mask = Image.open(io.BytesIO(base64.b64decode(request['mask']))).convert('L')
            if image.size != (512,512) or mask.size != (512,512):
                raise ValueError('Images must be 512x512')
            steps = int(request.get('steps',6))
            def progress(_pipe, step, timestep, values):
                emit(kind='progress', id=job, step=step+1, total=steps)
                return values
            with torch.inference_mode():
                result = pipe(prompt=request['prompt'],
                    negative_prompt='blurry, deformed, distorted, low quality, text, watermark',
                    image=image, mask_image=mask, width=512, height=512,
                    num_inference_steps=steps, guidance_scale=1.,
                    generator=torch.Generator(device='cpu').manual_seed(int(request.get('seed',42))),
                    callback_on_step_end=progress, output_type='latent')
                if not torch.isfinite(result.images).all():
                    raise FloatingPointError('Non-finite diffusion latents')
                # Decode at full precision on Metal to avoid FP16 VAE overflow.
                pipe.vae.to(dtype=torch.float32)
                decoded=pipe.vae.decode(result.images.float()/pipe.vae.config.scaling_factor,
                                        return_dict=False)[0]
                if not torch.isfinite(decoded).all():
                    raise FloatingPointError('Non-finite decoded image')
                generated=pipe.image_processor.postprocess(decoded,output_type='pil')[0]
                pipe.vae.to(dtype=torch.float16)
            # Preserve all unselected pixels exactly; soften only inside selection.
            feather = mask.filter(ImageFilter.GaussianBlur(3))
            feather = Image.composite(feather, Image.new('L',mask.size),mask)
            output = Image.composite(generated,image,feather)
            # Check the actual composited output, including the original person,
            # rather than discarded model pixels outside the user's selection.
            import numpy as np
            with torch.inference_mode():
                clip=pipe.feature_extractor([output],return_tensors='pt').pixel_values.to('mps',dtype=torch.float16)
                _,flags=pipe.safety_checker(images=np.asarray(output)[None].astype(np.float32)/255.,clip_input=clip)
            if flags[0]:
                emit(kind='error',id=job,message='โมเดลไม่ส่งคืนภาพนี้ ลองเปลี่ยนคำอธิบาย');continue
            buffer=io.BytesIO();output.save(buffer,format='PNG')
            emit(kind='result',id=job,image=base64.b64encode(buffer.getvalue()).decode(),
                 seconds=round(time.monotonic()-started,2))
            torch.mps.empty_cache()
        except Exception as exc:
            emit(kind='error',id=job,message='สร้างภาพไม่สำเร็จ: '+type(exc).__name__)
            pipe.vae.to(dtype=torch.float16)
            torch.mps.empty_cache()


if __name__ == '__main__':
    main()
