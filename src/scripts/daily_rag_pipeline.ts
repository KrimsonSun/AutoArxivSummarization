import { fetchDailyCsPapers } from '../lib/arxiv';
import { extractFineGrainedMetadata } from '../model/extract';
import { upsertPaperSolution } from '../model/pinecone';

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
            // arXiv URL structure: http://arxiv.org/abs/1234.56789
            // PDF URL: http://arxiv.org/pdf/1234.56789.pdf
            const pdfUrl = `https://arxiv.org/pdf/${paper.arxiv_id}.pdf`;

            // Step A: Parse PDF and Extract Metadata using Gemini File API (Combined Step)
            console.log('  -> Extracting fine-grained metadata with Gemini...');
            const metadata = await extractFineGrainedMetadata(
                pdfUrl,
                paper.title,
                paper.arxiv_id,
                paper.published_date
            );

            if (!metadata) {
                console.warn(`  -> Gemini metadata extraction failed. Skipping paper.`);
                failCount++;
            } else {
                // Optional: fallback domain from arxiv if Gemini fails to determine
                if (!metadata.domain || metadata.domain.length === 0) {
                    metadata.domain = ['cs.LG', 'cs.AI']; // General guess for CS daily fetch
                }

                // Step B: Upsert into Pinecone
                console.log('  -> Upserting solution into Pinecone...');
                await upsertPaperSolution(metadata);

                console.log('  -> Successfully processed & indexed!');
                successCount++;
            }
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
