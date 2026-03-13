#!/bin/bash
# Install Docker
apt-get update
apt-get install -y docker.io

# Create application directory
mkdir -p /opt/docling-api
cd /opt/docling-api

# Create main.py
cat << 'EOF' > main.py
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
    
    response = requests.get(url)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Could not fetch PDF")
        
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(response.content)
        temp_path = temp_file.name
        
    try:
        result = converter.convert(temp_path)
        markdown = result.document.export_to_markdown()
        return {"markdown": markdown}
    finally:
        os.remove(temp_path)
EOF

# Create requirements.txt
cat << 'EOF' > requirements.txt
fastapi
uvicorn
docling
requests
python-multipart
EOF

# Create Dockerfile
cat << 'EOF' > Dockerfile
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    poppler-utils \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
EOF

# Build and run the container
docker build -t docling-api .
docker run -d -p 80:80 --restart always docling-api
