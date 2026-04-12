#!/bin/bash
set -e

echo "==========================================="
echo "🚀 Starting AutoArxivSummarization System  "
echo "==========================================="

# Check if .env.local exists
if [ ! -f .env.local ]; then
    echo "⚠️ Warning: .env.local file not found. Cloud dependencies (Pinecone, Supabase) might fail."
    echo "Please ensure you have configured your environment variables."
    echo "==========================================="
fi

echo "[1/2] Installing NPM dependencies..."
npm install

echo "[2/2] Starting Next.js Web Server..."
npm run dev
