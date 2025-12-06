from huggingface_hub import snapshot_download
import os
import time

models = [
    "HelpingAI/HELVETE-3B",
    "prithivMLmods/Security-Llama3.2-3B-GGUF",
    "stabilityai/stable-code-3b",
    "GetSoloTech/Gemma3-Code-Reasoning-4B-GGUF"
]

base_dir = "models"

for model_id in models:
    print(f"Downloading {model_id}...")
    success = False
    retries = 3
    while not success and retries > 0:
        try:
            local_dir = os.path.join(base_dir, model_id)
            snapshot_download(repo_id=model_id, local_dir=local_dir, resume_download=True)
            print(f"Successfully downloaded {model_id} to {local_dir}")
            success = True
        except Exception as e:
            print(f"Failed to download {model_id}: {e}")
            retries -= 1
            if retries > 0:
                print(f"Retrying in 5 seconds... ({retries} retries left)")
                time.sleep(5)
            else:
                print(f"Giving up on {model_id}")
