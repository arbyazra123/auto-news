#!/bin/bash
# Automated daily stock analysis

set -e  # Exit on error

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting daily stock analysis automation"

# Check if already in the 'ml' environment, if not activate it
if [ "$CONDA_DEFAULT_ENV" != "ml" ]; then
    log "Activating conda environment 'ml'"
    source /home/arboapin/miniconda3/etc/profile.d/conda.sh
    conda activate ml
else
    log "Already in conda environment 'ml'"
fi

# Step 1 & 2: Prepare news
log "Running news preparation"
rm -f news.txt
rm -f news_condensed.txt
bash prepare_news.sh

# Step 3: Run analysis
log "Running Claude Code analysis"
cat analysis_prompt.txt | claude -p --dangerously-skip-permissions

log "Analysis complete"
log "Daily report generated at: daily_report.md"

conda deactivate
log "Conda environment deactivated"
