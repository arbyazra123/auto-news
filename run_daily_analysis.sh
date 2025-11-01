#!/bin/bash
# Complete automated workflow for daily stock analysis

set -e  # Exit on error

echo "======================================"
echo "   Daily Stock Analysis Automation"
echo "======================================"
echo ""

# Check if already in the 'ml' environment, if not activate it
if [ "$CONDA_DEFAULT_ENV" != "ml" ]; then
    echo "🔄 Activating conda environment 'ml'..."
	source /home/arboapin/miniconda3/etc/profile.d/conda.sh
    conda activate ml
else
    echo "✓ Already in conda environment 'ml'"
fi

# Step 1 & 2: Prepare news
echo "📰 Running news preparation..."
rm -f news.txt
rm -f news_condensed.txt
bash prepare_news.sh

echo ""
echo "======================================"
echo "🤖 Step 3: Running Claude Code analysis..."
echo "======================================"
echo ""

# Step 3: Invoke Claude Code to analyze and generate report
# Using the Claude Code CLI with the prompt
cat analysis_prompt.txt | claude -p --dangerously-skip-permissions

echo ""
echo "======================================"
echo "✅ Analysis complete!"
echo "======================================"
echo ""
echo "📊 Daily report generated at: daily_report.md"
conda deactivate
