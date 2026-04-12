import { NextResponse } from 'next/server';
import { fetchRandomCsPaper } from '@/lib/arxiv';
import { summarizePaper } from '@/lib/llm';
import { dbOps } from '@/lib/db';
import { sendDailySummary } from '@/lib/email';
import { revalidatePath } from 'next/cache';
import { runAdjudicator } from '../../../../Adjudicator/index';

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const forceUpdate = searchParams.get('force') === 'true';

    // 0. Check Authorization (Optional but recommended)
    const authHeader = request.headers.get('authorization');
    if (process.env.CRON_SECRET && !forceUpdate && authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    try {
        console.log('Starting daily job...');

        // 1. Fetch random paper
        const paper = await fetchRandomCsPaper();
        if (!paper) {
            return NextResponse.json({ error: 'Failed to fetch paper' }, { status: 500 });
        }

        console.log('Fetched paper:', paper.title);

        // 2. Summarize paper — sends full PDF to Gemini, falls back to abstract
        const bilingualSummary = await summarizePaper(paper.title, paper.abstract, paper.arxiv_id);
        if (!bilingualSummary) {
            return NextResponse.json({ error: 'Failed to summarize paper' }, { status: 500 });
        }

        console.log('Generated bilingual summary.');

        // 2.5 Adjudicator logical breakdown
        console.log('Running Adjudicator Analysis...');
        const adjudicatorResult = await runAdjudicator(paper.title, paper.abstract, "");
        if (adjudicatorResult) {
            console.log('Adjudicator analysis completed successfully.');
        } else {
            console.log('Adjudicator analysis failed or was skipped.');
        }

        // 3. Save to DB
        await dbOps.savePaper({
            ...paper,
            authors: paper.authors.join(', '),
            summary_zh: bilingualSummary.zh,
            summary_en: bilingualSummary.en,
            adjudicator_data: adjudicatorResult ? JSON.stringify(adjudicatorResult) : undefined
        });

        console.log('Saved to database.');

        // 4. Purge Next.js Cache for the home page
        revalidatePath('/');

        // 5. Notify subscribers via Brevo
        const subscribers = await dbOps.getAllSubscribers();
        console.log(`Sending to ${subscribers.length} subscribers...`);

        for (const sub of subscribers) {
            await sendDailySummary(
                sub.email,
                paper.title,
                bilingualSummary.zh,
                bilingualSummary.en,
                paper.url,
                sub.language ?? 'zh',
                adjudicatorResult
            );
        }

        return NextResponse.json({
            success: true,
            paper: paper.title,
            summaries: {
                zh: bilingualSummary.zh.substring(0, 50) + '...',
                en: bilingualSummary.en.substring(0, 50) + '...'
            }
        });
    } catch (error) {
        console.error('Job failed:', error);
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
    }
}
