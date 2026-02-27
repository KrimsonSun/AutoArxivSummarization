import { NextResponse } from 'next/server';
import { fetchRandomCsPaper } from '@/lib/arxiv';
import { summarizePaper } from '@/lib/llm';
import { dbOps } from '@/lib/db';
import { sendDailySummary } from '@/lib/email';

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

        // 2. Summarize paper (Bilingual)
        const bilingualSummary = await summarizePaper(paper.title, paper.abstract);
        if (!bilingualSummary) {
            return NextResponse.json({ error: 'Failed to summarize paper' }, { status: 500 });
        }

        console.log('Generated bilingual summary.');

        // 3. Save to DB
        dbOps.savePaper({
            ...paper,
            authors: paper.authors.join(', '),
            summary_zh: bilingualSummary.zh,
            summary_en: bilingualSummary.en
        });

        console.log('Saved to database.');

        // 4. Notify Prefect for each subscriber
        const subscribers = dbOps.getAllSubscribers();
        console.log(`Notifying Prefect for ${subscribers.length} subscribers...`);

        for (const sub of subscribers) {
            await sendDailySummary(
                sub.email,
                paper.title,
                bilingualSummary.zh,
                bilingualSummary.en,
                paper.url
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
