from huggingface_hub import hf_hub_download

model_name = "tarun7r/Finance-Llama-8B-q4_k_m-GGUF"  # Check for the correct repository
model_file = "Finance-Llama-8B-GGUF-q4_K_M.gguf"     # Exact GGUF filename

model_path = hf_hub_download(
    repo_id=model_name,
    filename=model_file,
)