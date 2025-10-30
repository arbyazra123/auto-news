import faiss
import numpy as np
from sentence_transformers import CrossEncoder, SentenceTransformer
# from mlx_lm import load, generate
# from llama_cpp import Llama
from transformers import AutoModelForCausalLM, AutoTokenizer

# model_name = "tarun7r/Finance-Llama-8B-q4_k_m-GGUF"  # Check for the correct repository
# model_file = "Finance-Llama-8B-GGUF-q4_K_M.gguf"     # Exact GGUF filename

# llm = Llama(
#     model_path="/Users/defdef/.cache/huggingface/hub/models--tarun7r--Finance-Llama-8B-q4_k_m-GGUF/snapshots/912cf756ca91c5f68ad7a04b44323476b5337000/Finance-Llama-8B-GGUF-q4_K_M.gguf",
#     n_ctx=8192,           # Context window size
#     n_threads=8,          # CPU threads for inference
#     n_gpu_layers=0,      # Offload all layers to GPU
#     verbose=False         # Disable verbose logging
# )

tokenizer = AutoTokenizer.from_pretrained("unsloth/mistral-7b-instruct-v0.3-bnb-4bit")
model = AutoModelForCausalLM.from_pretrained("unsloth/mistral-7b-instruct-v0.3-bnb-4bit")

# model, tokenizer = load("mlx-community/Mistral-7B-Instruct-v0.3-4bit")

# Load embedding model (fast & good multilingual)
embedder = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank(query, retrieved_texts, top_n=3):
    # Create pairs: (query, candidate)
    pairs = [(query, text) for text in retrieved_texts]
    
    # Predict relevance scores (higher = more relevant)
    scores = reranker.predict(pairs)
    
    # Sort by descending score
    ranked = sorted(zip(retrieved_texts, scores), key=lambda x: x[1], reverse=True)
    
    # Return top_n passages
    return [text for text, _ in ranked[:top_n]]

def load_articles(filepath="news.txt"):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    # Split by markers
    raw_articles = text.split("### Article Start")
    articles = []
    for raw in raw_articles:
        if "### Article End" not in raw:
            continue
        chunk = raw.split("### Article End")[0].strip()
        if chunk:
            articles.append(chunk)
    return articles

def build_faiss_index(articles):
    embeddings = embedder.encode(articles, convert_to_numpy=True,show_progress_bar=True,
    batch_size=1,
    normalize_embeddings=True,
    num_workers=0)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    return index, embeddings

def retrieve(query, articles, index, k=3):
    q_emb = embedder.encode([query], convert_to_numpy=True)
    D, I = index.search(q_emb, k)
    return [articles[i] for i in I[0]]


def ask_llm(context, query):
    prompt = f"""
You are a financial assistant analyzing Indonesian stock news.

Context:
{context}

User Question:
{query}

Respond in this format:
Action: <Buy/Sell/Hold>
Reason: <detailed reasoning with exact date (dd-MMMM-yyyy)>
    """

    #MLX
    #result = ""
    #for token in generate(model, tokenizer, prompt, max_tokens=512):
    #    result += token
    # Generate response
    #return result

    #GGUF
    # output = llm(
    #     prompt,
    #     max_tokens=2500,       # Limit response length
    #     temperature=0.7,      # Creativity control
    #     top_p=0.9,            # Nucleus sampling
    #     echo=False,           # Return only the completion (not prompt)
    #     stop=["###"]          # Stop at "###" to avoid extra text
    # )

    # # Extract and print the response
    # response = output["choices"][0]["text"].strip()

    ##GENERAL
    # inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).input_ids.to(model.device)
    # outputs = model.generate(input_ids=inputs, max_length=4096)[0]
    # answer_start = int(inputs.shape[-1])
    # pred = tokenizer.decode(outputs[answer_start:], skip_special_tokens=True)

    input_ids = tokenizer(prompt, return_tensors="pt").input_ids
    output = model.generate(input_ids, max_length=512)
    resp = tokenizer.decode(output[0], skip_special_tokens=True)
    return resp


# Load and index articles
articles = load_articles("news.txt")
index, _ = build_faiss_index(articles)

# Example user query
query = "What's the conclusion? What stock that i need to Buy/Hold/Sell "

# Retrieve relevant articles
retrieved = retrieve(query, articles, index, k=20)

reranked = rerank(query, retrieved)[:3]
context = "\n\n".join(reranked)
# Concatenate retrieved context
# context = "\n\n".join(retrieved)

print(f"Context: {context}")

# Ask LLM for recommendation
answer = ask_llm(context, query)

print("📊 Rekomendasi:")
print(answer)
