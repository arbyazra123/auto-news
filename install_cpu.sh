#!/bin/bash
# Install dependencies for CPU-only Ubuntu server
# This ensures PyTorch CPU version is used (no CUDA/GPU dependencies)

echo "Installing PyTorch CPU version..."
pip install torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu

echo "Installing other dependencies..."
# Install everything except torch (already installed above)
pip install requests==2.31.0 \
    beautifulsoup4==4.12.3 \
    pymilvus==2.4.3 \
    sentence-transformers==2.5.1 \
    transformers==4.38.2 \
    numpy==1.26.4

echo "Verifying CPU-only installation..."
python3 -c "import torch; print(f'PyTorch version: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}')"

echo "Installation complete!"
