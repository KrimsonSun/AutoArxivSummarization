import { fetchRandomCsPaper } from '../lib/arxiv';
import { summarizePaper } from '../lib/llm';
import { runAdjudicator } from '../../Adjudicator/index';
import { dbOps } from '../lib/db';
import { sendDailySummary } from '../lib/email';

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

async function runDailyHighlight() {
    console.log(`\n===========================================`);
    console.log(`🎯 SELECTING DAILY HIGHLIGHT`);
    console.log(`===========================================`);
    
    try {
        // ── Step 1: Fetch a paper ──────────────────────────────────────────
        let highlight = await fetchRandomCsPaper();
        if (!highlight) {
            console.warn("[Fallback] arXiv fetch failed. Grabbing latest paper from DB...");
            const latestDbPaper = await dbOps.getLatestPaper();
            if (latestDbPaper) {
                highlight = {
                    arxiv_id: latestDbPaper.arxiv_id,
                    title: latestDbPaper.title,
                    abstract: latestDbPaper.abstract,
                    url: latestDbPaper.url,
                    published_date: latestDbPaper.published_date,
                    authors: latestDbPaper.authors.split(', ')
                };
            }
        }
        if (!highlight) {
            console.error("No paper available. Aborting.");
            process.exit(1);
        }
        console.log(`Picked for Highlight: ${highlight.title}`);

        // ── Step 2: Summarize — retry once on Gemini 503 ──────────────────
        let bilingualSummary = await summarizePaper(highlight.title, highlight.abstract, highlight.arxiv_id);
        if (!bilingualSummary) {
            console.warn("[Retry] Gemini summarization failed (503?). Retrying in 10s...");
            await sleep(10000);
            bilingualSummary = await summarizePaper(highlight.title, highlight.abstract, highlight.arxiv_id);
        }
        if (!bilingualSummary) {
            // Both attempts failed — abort entirely. Do NOT write garbage to DB.
            // The website will keep showing the previous successful paper.
            console.error("[Abort] Gemini summarization failed after retry. No data saved, no email sent.");
            process.exit(0); // exit 0 so Cloud Run doesn't mark this as a system failure
        }
        console.log("Summary generated successfully.");

        // ── Step 3: Adjudicator — non-fatal ───────────────────────────────
        let adjudicatorResult = null;
        try {
            adjudicatorResult = await runAdjudicator(highlight.title, highlight.abstract, "");
            if (adjudicatorResult) {
                console.log("Adjudicator analysis completed.");
            } else {
                console.warn("[Adjudicator] Returned null — saving paper without analysis.");
            }
        } catch (adjErr: any) {
            console.warn("[Adjudicator] Non-fatal error:", adjErr.message ?? adjErr);
        }

        // ── Step 4: Save to DB ────────────────────────────────────────────
        await dbOps.savePaper({
            ...highlight,
            authors: highlight.authors.join(', '),
            summary_zh: bilingualSummary.zh,
            summary_en: bilingualSummary.en,
            adjudicator_data: adjudicatorResult ? JSON.stringify(adjudicatorResult) : undefined
        });
        console.log('Saved highlight to DB.');

        // ── Step 5: Send emails ───────────────────────────────────────────
        const subscribers = await dbOps.getAllSubscribers();
        console.log(`Sending to ${subscribers.length} subscribers...`);
        const emailResults = await Promise.allSettled(
            subscribers.map(sub =>
                sendDailySummary(
                    sub.email,
                    highlight!.title,
                    bilingualSummary!.zh,
                    bilingualSummary!.en,
                    highlight!.url,
                    sub.language ?? 'zh',
                    adjudicatorResult
                )
            )
        );
        const sent = emailResults.filter(r => r.status === 'fulfilled').length;
        const failed = emailResults.filter(r => r.status === 'rejected').length;
        console.log(`Email broadcast complete: ${sent} sent, ${failed} failed.`);

    } catch (err) {
        console.error('Failed to run Daily Highlight process:', err);
        process.exit(1);
    }
    
    process.exit(0);
}

runDailyHighlight().catch(err => {
    console.error('Fatal highlight error:', err);
    process.exit(1);
});
