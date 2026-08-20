#!/bin/bash
set -e

# Ensure repository uses merge strategy for pull
git config pull.rebase false

echo "🔄 Fetching and syncing latest remote changes..."
git pull --no-rebase --no-edit -X ours origin main

echo "🚀 Pushing to GitHub Pages..."
git push origin main

echo "🎉 Done! Successfully published latest changes to GitHub Pages."
