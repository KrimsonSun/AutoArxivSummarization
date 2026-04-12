import { fetchRandomCsPaper } from '../lib/arxiv';
import { summarizePaper } from '../lib/llm';
import { runAdjudicator } from '../../Adjudicator/index';
import { dbOps } from '../lib/db';
import { sendDailySummary } from '../lib/email';

async function runDailyHighlight() {
    console.log(`\n===========================================`);
    console.log(`🎯 SELECTING DAILY HIGHLIGHT`);
    console.log(`===========================================`);
    
    try {
        let highlight = await fetchRandomCsPaper();
        if (!highlight) {
            console.warn("[Fallback] arXiv random fetch failed (likely rate limited). Grabbing latest paper from local Supabase DB...");
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
            console.error("No random paper could be fetched, and DB is empty. Aborting.");
            process.exit(1);
        }
        
        console.log(`Picked for Highlight: ${highlight.title}`);
        const bilingualSummary = await summarizePaper(highlight.title, highlight.abstract, highlight.arxiv_id);
        const adjudicatorResult = await runAdjudicator(highlight.title, highlight.abstract, "");
        
        await dbOps.savePaper({
            ...highlight,
            authors: highlight.authors.join(', '),
            summary_zh: bilingualSummary?.zh || "摘要生成失败...",
            summary_en: bilingualSummary?.en || "Summary generation failed...",
            adjudicator_data: adjudicatorResult ? JSON.stringify(adjudicatorResult) : undefined
        });
        console.log('Saved highlight to DB.');

        const subscribers = await dbOps.getAllSubscribers();
        console.log(`Sending to ${subscribers.length} subscribers...`);
        for (const sub of subscribers) {
            await sendDailySummary(
                sub.email,
                highlight.title,
                bilingualSummary?.zh || "摘要生成失败...",
                bilingualSummary?.en || "Summary generation failed...",
                highlight.url,
                sub.language ?? 'zh',
                adjudicatorResult
            );
        }
        console.log('Email broadcast complete.');
    } catch (err) {
        console.error('Failed to run Daily Highlight process:', err);
        process.exit(1);
    }
    
    // Explicitly exit so the postgres connection pool doesn't hang Cloud Run
    process.exit(0);
}

runDailyHighlight().catch(err => {
    console.error('Fatal highlight error:', err);
    process.exit(1);
});
