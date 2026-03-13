# Deploying Docling on Google Cloud Platform (GCP)

This project uses [Docling](https://github.com/DS4SD/docling) to convert PDF research papers into structured Markdown. Because document parsing can be resource-intensive, we host Docling separately on GCP where it can be scaled and accessed via a REST API.

## Recommended Architecture: Cloud Run

**Why Cloud Run?**
- Scale to zero: You only pay when documents are actively being parsed.
- Fully managed: No servers to maintain.
- Can be configured with enough CPU/RAM to handle complex PDFs.

### Prerequisites

1. Install Google Cloud SDK (`gcloud`).
2. Authenticate: `gcloud auth login`
3. Set your project: `gcloud config set project YOUR_PROJECT_ID`

### Step 1: Create a Wrapper for Docling (Optional but Recommended)

Since Docling is primarily a Python library, you need a simple HTTP server (like FastAPI or Flask) to wrap it.

```python
# main.py
from fastapi import FastAPI, HTTPException
from docling.document_converter import DocumentConverter
import requests
import tempfile
import os

app = FastAPI()
converter = DocumentConverter()

@app.post("/convert")
async def convert_pdf(request: dict):
    url = request.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Missing URL")
    
    # Download the PDF temporarily
    response = requests.get(url)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Could not fetch PDF")
        
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(response.content)
        temp_path = temp_file.name
        
    try:
        # Convert using Docling
        result = converter.convert(temp_path)
        markdown = result.document.export_to_markdown()
        return {"markdown": markdown}
    finally:
        os.remove(temp_path)
```

Create a `Dockerfile`:
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# System dependencies often required for document processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    poppler-utils \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Step 2: Build and Deploy to Cloud Run

1. Build and push the container to Google Artifact Registry:
   ```bash
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/docling-api
   ```

2. Deploy the container to Cloud Run:
   ```bash
   gcloud run deploy docling-api \
     --image gcr.io/YOUR_PROJECT_ID/docling-api \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --memory 8Gi \
     --cpu 4 \
     --timeout 300
   ```
   **Important Settings:**
   - `--memory 8Gi --cpu 4`: OCR and layout analysis are heavy. Providing 4 CPUs and 8GB RAM ensures the conversion completes smoothly.
   - `--timeout 300`: PDF conversion can take time, easily 30-60 seconds for larger ArXiv papers. Increase the timeout to 5 minutes so requests don't randomly fail.

### Step 3: Configure Your App

Get the deployed URL from the Cloud Run output (e.g., `https://docling-api-xxxxx-uc.a.run.app`).

Add it to your `.env` file in the main application:
```
DOCLING_API_URL=https://docling-api-xxxxx-uc.a.run.app
```

## Alternative: Compute Engine (e2-standard-4)

If you prefer a persistent VM instead of serverless, an `e2-standard-4` (4 vCPU, 16GB Memory) instance is the most cost-effective machine type.

1. Launch a Compute Engine VM with Ubuntu.
2. Install Docker.
3. Build your image on the VM (or pull it from Artifact Registry).
4. Run the container: `docker run -d -p 80:8080 docling-api`
5. Configure your network security group to allow inbound traffic on port 80.
6. Set `DOCLING_API_URL=http://YOUR_VM_IP` in your `.env`.

*Note: You pay for Compute Engine instances 24/7, whereas Cloud Run only charges when endpoints are invoked.*
