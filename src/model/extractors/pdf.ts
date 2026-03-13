import 'dotenv/config';

/**
 * Attempts to parse the PDF using a self-hosted Docling endpoint.
 */
export async function extractPdfWithDocling(arxivId: string): Promise<string | null> {
    const doclingUrl = process.env.DOCLING_API_URL;
    
    if (!doclingUrl) {
        console.warn(`[PDF Extractor] DOCLING_API_URL is not set. Skipping Docling PDF extraction.`);
        return null;
    }

    const pdfUrl = `https://arxiv.org/pdf/${arxivId}`;
    
    try {
        console.log(`[PDF Extractor] Sending request to Docling API for ${pdfUrl}...`);
        
        // Note: The specific request format depends on how you deploy Docling (e.g. Docling-Server or custom wrapper)
        // Here we assume a typical POST endpoint that accepts a document URL and returns markdown.
        // Adjust this payload based on your exact Docling API spec.
        const response = await fetch(`${doclingUrl}/convert`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                url: pdfUrl,
                format: 'markdown' 
            })
        });

        if (!response.ok) {
            console.log(`[PDF Extractor] Docling API failed (status: ${response.status})`);
            return null;
        }

        const data = await response.json();
        
        if (data && data.markdown) {
            console.log(`[PDF Extractor] Successfully converted PDF to Markdown via Docling. Length: ${data.markdown.length}`);
            return data.markdown;
        } else {
            console.log(`[PDF Extractor] Docling API response missing 'markdown' field.`);
            return null;
        }
    } catch (error) {
        console.error(`[PDF Extractor] Error processing PDF with Docling for ${arxivId}:`, error);
        return null;
    }
}
