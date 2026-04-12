import { fetchDailyCsPapersIncremental } from '../lib/arxiv';
import { extractHtml } from '../model/extractors/html';
import { extractLatex } from '../model/extractors/latex';
import { extractPdfWithDocling } from '../model/extractors/pdf';
import { upsertFullPaperChunks, checkPaperExists } from '../model/pinecone';
import { dbOps } from '../lib/db';
import fs from 'fs';
import path from 'path';

// Target a high paper limit as requested by the user
const LIMIT = process.env.LIMIT ? parseInt(process.env.LIMIT, 10) : 10000;
const CONCURRENCY = 2; // Reduced to 2 to prevent overloading the Docling VM embedding engine
const LOG_FILE = path.join(process.cwd(), 'ingestion_log.json');

async function processPaper(paper: any, currentCount: number, totalLimit: number) {
    console.log(`\n[${currentCount}/${totalLimit}] Starting: ${paper.title} (${paper.arxiv_id})`);
    
    try {
        // Step 0: Check if paper already exists in Pinecone
        const exists = await checkPaperExists(paper.arxiv_id);
        if (exists) {
            console.log(`[${paper.arxiv_id}] Already indexed. Skipping.`);
            return { success: true, arxiv_id: paper.arxiv_id, method: "Skipped (Exists)" };
        }

        // Step 1: Extract Text (HTML -> LaTeX -> PDF)
        let textSource: string | null = await extractHtml(paper.arxiv_id);
        let method = "HTML";

        if (!textSource) {
            textSource = await extractLatex(paper.arxiv_id);
            method = "LaTeX";
        }

        if (!textSource) {
            textSource = await extractPdfWithDocling(paper.arxiv_id);
            if (textSource === "[OVERSIZE_SKIP]") {
                console.log(`[${paper.arxiv_id}] Skipped Pinecone ingestion due to excessive PDF size. Logging to Supabase...`);
                await dbOps.savePaper({
                    ...paper,
                    authors: paper.authors.join(', '),
                    summary_zh: '【系统保护】由于原论文 PDF 过大(>5MB)，系统为防止云节点崩溃已主动拦截该文献的向量入库。',
                    summary_en: '[Skipped] PDF exceptionally large. Passed over to strictly prevent Out-of-Memory limits.',
                    adjudicator_data: JSON.stringify({ error: "OOM Protection: Oversized PDF skipped from Docling and Pinecone processing." })
                });
                return { success: true, arxiv_id: paper.arxiv_id, method: "Skipped (Oversize)" };
            }
            method = "Docling PDF";
        }

        if (!textSource) {
            console.warn(`[${paper.arxiv_id}] All extraction methods failed. Using abstract.`);
            textSource = paper.abstract || "";
            method = "Abstract Only";
        }

        const finalText: string = textSource!!; // Guaranteed non-null now
        console.log(`[${paper.arxiv_id}] Text extracted via ${method} (${finalText.length} chars).`);

        // Step 2: Chunk and Embed
        await upsertFullPaperChunks(paper, finalText);
        
        return { success: true, arxiv_id: paper.arxiv_id, method };
    } catch (error: any) {
        console.error(`[${paper.arxiv_id}] Failed:`, error.message);
        return { success: false, arxiv_id: paper.arxiv_id, error: error.message };
    }
}

async function runDailyRagPipeline() {
    console.log(`===========================================`);
    console.log(`🚀 DAILY RAG INGESTION: TARGET ${LIMIT} PAPERS`);
    console.log(`🚀 MODE: INCREMENTAL STREAMING`);
    console.log(`===========================================`);



    const startTime = Date.now();
    const results: any[] = [];
    let processedSoFar = 0;

    // 1 & 2. Fetch and Process papers incrementally
    const finalTotalFetched = await fetchDailyCsPapersIncremental(LIMIT, async (pagePapers) => {
        // Process each page of papers with concurrency
        for (let i = 0; i < pagePapers.length; i += CONCURRENCY) {
            const batch = pagePapers.slice(i, i + CONCURRENCY);
            const batchPromises = batch.map((p) => {
                processedSoFar++;
                return processPaper(p, processedSoFar, LIMIT);
            });
            
            const batchResults = await Promise.all(batchPromises);
            results.push(...batchResults);

            // Progress update
            const successful = results.filter(r => r.success).length;
            const percent = ((processedSoFar / LIMIT) * 100).toFixed(1);
            const elapsed = Math.round((Date.now() - startTime) / 1000);
            console.log(`\n--- PROGRESS: ${processedSoFar}/${LIMIT} (${percent}%) | Success: ${successful} | Elapsed: ${elapsed}s ---`);
        }
    });

    // 3. Final Summary
    const successful = results.filter(r => r.success).length;
    const failed = results.filter(r => !r.success).length;
    const durationMins = ((Date.now() - startTime) / 60000).toFixed(1);

    console.log(`\n===========================================`);
    console.log(`✅ INGESTION COMPLETE`);
    console.log(`- Total Time: ${durationMins} minutes`);
    console.log(`- Successfully Processed: ${successful}`);
    console.log(`- Failed: ${failed}`);
    console.log(`- Total Metadata Records Fetched: ${finalTotalFetched}`);
    console.log(`===========================================`);

    // Save detailed results for audit
    try {
        fs.writeFileSync(LOG_FILE, JSON.stringify({
            timestamp: new Date().toISOString(),
            totalFetched: finalTotalFetched,
            successful,
            failed,
            durationMins,
            details: results
        }, null, 2));
        console.log(`Detailed logs saved to: ${LOG_FILE}`);
    } catch (err) {
        console.error('Failed to save log file:', err);
    }
}

runDailyRagPipeline().catch(err => {
    console.error('Fatal pipeline error:', err);
    process.exit(1);
});
