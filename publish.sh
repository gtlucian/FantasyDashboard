#!/bin/bash
# One-click foolproof sync and publish script
set -e

echo "🔄 Fetching and syncing latest remote GitHub Actions changes..."
git pull --no-edit -X ours origin main

echo "🚀 Pushing to GitHub Pages..."
git push origin main

echo "🎉 Done! Successfully published latest changes to GitHub."
