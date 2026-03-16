import { fetchDailyCsPapers } from '../lib/arxiv';
import { extractHtml } from '../model/extractors/html';
import { extractLatex } from '../model/extractors/latex';
import { extractPdfWithDocling } from '../model/extractors/pdf';
import { extractFineGrainedMetadata } from '../model/extract';
import { upsertPaperSolution, upsertFullPaperChunks } from '../model/pinecone';

// Optional: you can run this with a limit like: limit=10 npm run rag:daily
const LIMIT = process.env.LIMIT ? parseInt(process.env.LIMIT, 10) : 1000;

async function runDailyRagPipeline() {
    console.log(`Starting Daily RAG Pipeline. Target paper count: ${LIMIT}`);

    // 1. Fetch papers from arXiv
    console.log('Fetching papers from arXiv...');
    const papers = await fetchDailyCsPapers(LIMIT);
    console.log(`Fetched ${papers.length} papers from arXiv.`);

    let successCount = 0;
    let failCount = 0;

    // 2. Process each paper sequentially
    for (let i = 0; i < papers.length; i++) {
        const paper = papers[i];
        console.log(`\n[${i + 1}/${papers.length}] Processing: ${paper.title} (${paper.arxiv_id})`);

        try {
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

            // Step B: Direct embedding of full text into chunks
            console.log(`  -> Chunking and upserting full paper text (${textSource.length} chars) into Pinecone...`);
            await upsertFullPaperChunks(paper, textSource);

            console.log('  -> Successfully processed & indexed!');
            successCount++;

        } catch (error) {
            console.error(`Error processing paper ${paper.arxiv_id}:`, error);
            failCount++;
        }

        // To comply with Gemini Free Tier limit of 15 Requests Per Minute (RPM),
        // we must wait just over 4 seconds between each paper.
        if (i < papers.length - 1) {
            console.log('  -> Waiting 4.1 seconds to respect API rate limits...');
            await new Promise(resolve => setTimeout(resolve, 4100)); 
        }
    }

    console.log('\n================================');
    console.log('Daily RAG Pipeline Complete');
    console.log(`Successfully Processed: ${successCount}`);
    console.log(`Failed: ${failCount}`);
    console.log('================================');
}

// Execute
runDailyRagPipeline().then(() => {
    process.exit(0);
}).catch(err => {
    console.error('Fatal error in daily RAG pipeline:', err);
    process.exit(1);
});
