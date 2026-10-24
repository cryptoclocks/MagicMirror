"""Download a pinned, safetensors-only MPS inpainting model (one-time network)."""
from pathlib import Path
from huggingface_hub import snapshot_download
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    snapshot_download('stable-diffusion-v1-5/stable-diffusion-inpainting',
        revision='8a4288a76071f7280aedbdb3253bdb9e9d5d84bb',
        local_dir=str(ROOT/'.local-ai/model'),max_workers=2,
        allow_patterns=['model_index.json','*/config.json','*/preprocessor_config.json',
                        '*/scheduler_config.json','tokenizer/*','*/*.fp16.safetensors','README.md'])

    snapshot_download('latent-consistency/lcm-lora-sdv1-5',
        revision='cf2fced511dbe7e26c8d1d397e728fbab875db4b',
        local_dir=str(ROOT/'.local-ai/lcm'),
        allow_patterns=['pytorch_lora_weights.safetensors','README.md'])
