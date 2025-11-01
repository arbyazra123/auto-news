from llama_cpp import Llama

MODEL_PATH = "Qwen3-4B-Q6_K.gguf"  # Update this path

# Initialize the model
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=256,  # Context window
    n_threads=4,  # Number of CPU threads
    n_gpu_layers=0,  # Set to -1 to use GPU, 0 for CPU only
    verbose=True
)

output = llm(
    "test",
    max_tokens=256,
    temperature=0.7,
    # stop=True,
    # echo=False,
    # verbose=True
)

print(f"RESULT: {output['choices'][0]['text'].strip()}")
