#!/bin/bash
set -e

# Setup writable directories for appuser
mkdir -p /home/appuser/.claude
mkdir -p /app/data

# Set ownership
chown -R appuser:appuser /home/appuser/.claude
chown -R appuser:appuser /app/data
chmod 700 /home/appuser/.claude

# Start the application
exec "$@"
