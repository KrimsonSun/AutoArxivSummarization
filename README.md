# arXiv Ingestion Monitoring & Management Guide

This document provides instructions for monitoring and managing the persistent paper ingestion system running on the **Compute Engine VM (GCE)**.

## 🚀 Overview
The ingestion system has been migrated to a persistent Docker container on the `docling-vm` to bypass the 24-hour Cloud Run timeout. It is currently backfilling **10,000 papers**.

---

## 📺 Real-time Monitoring (Logs)
To see exactly what the ingestion engine is doing right now (titles, success/failure, extraction methods), run this command in your **local terminal**:

```bash
gcloud compute ssh docling-vm --zone us-central1-a --command "sudo docker logs -f arxiv-ingest-orchestrator"
```
*Note: You can close your terminal anytime; the process will continue running on the server.*

---

## 📊 Checking Progress (Total Stats)
To see the current total number of papers and vectors in your Pinecone index, run:

```bash
npx tsx -r dotenv/config src/scripts/check_stats.ts
```

---

## 🛠️ Management Commands (GCE)

### Stop the Ingestion
If you need to pause the backfill:
```bash
gcloud compute ssh docling-vm --zone us-central1-a --command "sudo docker stop arxiv-ingest-orchestrator"
```

### Restart the Ingestion
```bash
gcloud compute ssh docling-vm --zone us-central1-a --command "sudo docker start arxiv-ingest-orchestrator"
```

### Force a Clean Restart (Pulls latest image)
```bash
gcloud compute ssh docling-vm --zone us-central1-a --command "sudo docker rm -f arxiv-ingest-orchestrator && sudo docker run -d --name arxiv-ingest-orchestrator --restart always --network host -e LIMIT=10000 [ENV_VARS] gcr.io/arxiv-488704/arxiv-ingest-job:latest"
```

---

## 🏗️ Architecture
- **Worker Concurrency**: 5 (Optimized for 16GB RAM)
- **Deduplication**: Enabled (Automatically skips already-indexed arXiv IDs)
- **Local Services**: Communicates with Nomic (port 8001) and Docling (port 80) via `localhost`.
