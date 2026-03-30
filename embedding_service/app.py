
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
import torch.nn.functional as F
from sentence_transformers import SentenceTransformer

app = FastAPI(title="Nomic Embedding Service", version="1.0")

# Load Nomic model globally
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Loading nomic-embed-text-v1.5 on {device}...")
model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True, device=device)

class EmbedRequest(BaseModel):
    text: str
    task_type: str = "search_document" # Expected prefixes: 'search_query', 'search_document', 'clustering', 'classification'

@app.post("/embed")
async def get_embedding(req: EmbedRequest):
    try:
        # Nomic v1.5 requires prefixes for optimal performance
        prefix = f"{req.task_type}: " if req.task_type else ""
        full_text = prefix + req.text
        
        # 1. Generate standard 768-dim embeddings
        embeddings = model.encode([full_text], convert_to_tensor=True)[0]
        
        # 2. Slice to Nomic's official Matryoshka sub-dimensions (512, 256, 128, 64)
        # We target 512 as requested
        embeddings = embeddings[:512]
        
        # 3. Layer Normalization is required after slicing Nomic Matryoshka dimensions
        # as per official documentation
        embeddings = F.layer_norm(embeddings, normalized_shape=(embeddings.shape[0],))
        normalized_embeddings = F.normalize(embeddings, p=2, dim=0)
        
        return {
            "embedding": normalized_embeddings.tolist(),
            "dim": len(normalized_embeddings)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
