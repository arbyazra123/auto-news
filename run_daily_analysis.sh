#!/bin/bash
# Automated daily stock analysis

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting daily stock analysis automation"

# Check if conda is available and activate environment if needed
if command -v conda &> /dev/null; then
    if [ "$CONDA_DEFAULT_ENV" != "ml" ]; then
        log "Activating conda environment 'ml'"
        # Try to initialize conda (works for most installations)
        eval "$(conda shell.bash hook)" 2>/dev/null || true
        conda activate ml 2>/dev/null || log "Warning: Could not activate conda env 'ml', using current Python"
    else
        log "Already in conda environment 'ml'"
    fi
else
    log "Conda not found, using current Python environment"
fi

log "Running Claude Code analysis"
log "=== ENVIRONMENT DEBUG ==="
log "PATH: $PATH"
log "HOME: $HOME"
log "PWD: $(pwd)"
log "USER: $USER"
log "SHELL: $SHELL"
log "Claude location: $(which claude 2>&1)"
log "Claude version: $(claude --version 2>&1)"
log "========================"

# Step 1 & 2: Prepare news
log "Running news preparation"
rm -f news.txt
rm -f news_condensed.txt
bash prepare_news.sh

# Step 3: Run analysis
log "Running Claude Code analysis"

timeout 30m cat analysis_prompt.txt | claude -p --dangerously-skip-permissions

log "Analysis complete"
log "Daily report generated at: daily_report.md"

# Step 4: Trigger signal batch (PM buy/hold/sell + allocation) via stock API
log "Triggering signal batch via stock API"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:13052/ | grep -q "200"; then
    curl -s -X POST http://localhost:13052/api/signals/run \
        -H "Content-Type: application/json" \
        -d '{"analyze": true, "notes": "daily cron"}' \
        || log "Warning: signal batch trigger failed"
    log "Signal batch triggered (check /api/signals/status)"
else
    log "Warning: stock API not reachable on :13052, skipping signal batch"
fi

conda deactivate
log "Conda environment deactivated"
