import { searchPapersByQuery } from '../lib/arxiv';
import { extractHtml } from './extractors/html';
import { extractLatex } from './extractors/latex';
import { extractPdfWithDocling } from './extractors/pdf';
import { extractFineGrainedMetadata } from './extract';
import { upsertPaperSolution } from './pinecone';

// In a real scheduled job, you might want to paginate through 1000 items. 
// We process in smaller batches here to respect rate limits.
export async function runDailyIngestionBatch(batchSize: number = 50) {
    const query = "cat:cs.LG";

    console.log(`[Ingest] Fetching up to ${batchSize} latest papers from arXiv...`);
    // Note: For a 1000 paper batch, you would iterate with start=0, start=100, etc.
    const recentPapers = await searchPapersByQuery(query, batchSize);

    console.log(`[Ingest] Found ${recentPapers.length} papers. Starting processing pipeline...`);

    for (const paper of recentPapers) {
        try {
            console.log(`\n--- [${paper.arxiv_id}] ${paper.title.substring(0, 50)}... ---`);

            const pdfUrl = `https://arxiv.org/pdf/${paper.arxiv_id}`;

            // Step A: Parse document in priority: HTML -> LaTeX -> PDF (Docling)
            console.log(`[${paper.arxiv_id}] -> 1. Extracting text content...`);
            let textSource = await extractHtml(paper.arxiv_id);
            if (textSource) {
                console.log(`[${paper.arxiv_id}] -> Extraction succeeded via HTML.`);
            } else {
                textSource = await extractLatex(paper.arxiv_id);
                if (textSource) {
                    console.log(`[${paper.arxiv_id}] -> Extraction succeeded via LaTeX.`);
                } else {
                    textSource = await extractPdfWithDocling(paper.arxiv_id);
                    if (textSource) {
                        console.log(`[${paper.arxiv_id}] -> Extraction succeeded via Docling PDF.`);
                    } else {
                        console.warn(`[${paper.arxiv_id}] -> All extraction methods failed. Falling back to abstract.`);
                        textSource = paper.abstract;
                    }
                }
            }

            // Step B: Extract fine-grained limitations & solutions via Gemini
            console.log(`[${paper.arxiv_id}] -> 2. Deep extracting metadata via Gemini 2.5 Flash...`);
            const metadata = await extractFineGrainedMetadata(
                textSource,
                paper.title,
                paper.arxiv_id,
                paper.published_date
            );

            if (!metadata) {
                console.error(`[${paper.arxiv_id}] -> Metadata extraction failed, skipping.`);
                continue;
            }

            console.log(`[${paper.arxiv_id}] -> Target Problem identified: "${metadata.target_problem.substring(0, 40)}..."`);
            console.log(`[${paper.arxiv_id}] -> Found ${metadata.limitations.length} limitations.`);

            // Step C: Embed and Upsert to Pinecone Vector DB
            console.log(`[${paper.arxiv_id}] -> 3. Embedding and uploading to Pinecone...`);
            await upsertPaperSolution(metadata);

            console.log(`[${paper.arxiv_id}] -> SUCCESS!`);

            // Sleep briefly to prevent API rate limiting issues (Gemini/Pinecone/Reducto)
            await new Promise(resolve => setTimeout(resolve, 2000));
        } catch (e: any) {
            console.error(`Error processing paper ${paper.arxiv_id}:`, e.message);
        }
    }
}
