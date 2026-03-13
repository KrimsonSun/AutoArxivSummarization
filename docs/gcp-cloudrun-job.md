# Deploying Daily RAG Pipeline to Google Cloud Run Jobs

Because the daily RAG pipeline takes considerable time (processing 700 papers, respecting Gemini rate limits, and performing OCR/PDF parsing), it is perfectly suited for **Google Cloud Run Jobs**.

Unlike Cloud Run *Services* (which respond to HTTP requests like the Docling API), Cloud Run *Jobs* execute a script from start to finish and then spin down.

## Prerequisites

Ensure you've deployed the Docling API on Compute Engine (as per `docs/gcp-docling-deployment.md`) and have its IP address ready.

## Step 1: Build the Ingestion Image

We use a custom `Dockerfile.ingest` that pulls Node.js and installs the necessary OS dependencies for LaTeX extraction (`pandoc`, `tar`).

1. Build the image and push to Google Artifact Registry:
   ```bash
   # Replace YOUR_PROJECT_ID with your actual Google Cloud Project ID
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/arxiv-ingest-job -f Dockerfile.ingest .
   ```

## Step 2: Create the Cloud Run Job

Once the image is pushed, create the Cloud Run Job. We need to provide the environment variables it uses to function:

```bash
gcloud run jobs create daily-arxiv-ingest \
  --image gcr.io/YOUR_PROJECT_ID/arxiv-ingest-job \
  --region us-central1 \
  --timeout 3600s \
  --memory 2Gi \
  --cpu 1 \
  --set-env-vars="LIMIT=700,GEMINI_API_KEY=your_key,PINECONE_API_KEY=your_key,PINECONE_INDEX=arxivpdf,DOCLING_API_URL=http://35.224.62.21"
```

*Note:*
- `--timeout 3600s`: The job can run for up to 1 hour. Processing 700 papers with a 4.1s rate limit delay per paper takes at least ~48 minutes.
- `DOCLING_API_URL`: Points to the Compute Engine VM we spun up earlier.

## Step 3: Schedule the Job Daily

Use Google Cloud Scheduler to automatically trigger this job every day (e.g., at 2:00 AM UTC).

```bash
gcloud scheduler jobs create http daily-arxiv-ingest-trigger \
  --location us-central1 \
  --schedule="0 2 * * *" \
  --uri="https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/YOUR_PROJECT_ID/jobs/daily-arxiv-ingest:run" \
  --http-method=POST \
  --oauth-service-account-email="YOUR_COMPUTE_SERVICE_ACCOUNT@developer.gserviceaccount.com"
```

## Manual Execution (For Testing)

If you want to run the job immediately without waiting for the scheduler:

```bash
gcloud run jobs execute daily-arxiv-ingest --region us-central1
```
