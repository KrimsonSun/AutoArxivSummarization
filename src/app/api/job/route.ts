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

    // 0. Authorization
    const authHeader = request.headers.get('authorization');
    if (process.env.CRON_SECRET && !forceUpdate && authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    try {
        console.log('Starting daily job...');

        // 1. Fetch random paper — fallback to DB if arXiv rate-limits
        let paper = await fetchRandomCsPaper();
        if (!paper) {
            console.warn('[Fallback] arXiv fetch failed. Grabbing latest paper from Supabase DB...');
            const latestDbPaper = await dbOps.getLatestPaper();
            if (latestDbPaper) {
                paper = {
                    arxiv_id: latestDbPaper.arxiv_id,
                    title: latestDbPaper.title,
                    abstract: latestDbPaper.abstract,
                    url: latestDbPaper.url,
                    published_date: latestDbPaper.published_date,
                    authors: latestDbPaper.authors.split(', ')
                };
            }
        }

        if (!paper) {
            return NextResponse.json({ error: 'No paper available (arXiv blocked + DB empty)' }, { status: 500 });
        }

        console.log('Fetched paper:', paper.title);

        // 2. Summarize with gemini-3-flash-preview. Retry once on failure.
        //    If both attempts fail, abort — no point sending content-less email.
        let bilingualSummary = await summarizePaper(paper.title, paper.abstract, paper.arxiv_id);
        if (!bilingualSummary) {
            console.warn('[Retry] Gemini first attempt failed (503?). Retrying in 8s...');
            await new Promise(r => setTimeout(r, 8000));
            bilingualSummary = await summarizePaper(paper.title, paper.abstract, paper.arxiv_id);
        }
        if (!bilingualSummary) {
            console.error('[Abort] Both Gemini attempts failed. Aborting job — no email sent.');
            return NextResponse.json({ error: 'Gemini summarization failed after retry. Job aborted.' }, { status: 503 });
        }

        console.log('Summary ready.');

        // 3. Adjudicator — failure is non-fatal, email still sends
        console.log('Running Adjudicator Analysis...');
        let adjudicatorResult = null;
        try {
            adjudicatorResult = await runAdjudicator(paper.title, paper.abstract, '');
            if (adjudicatorResult) {
                console.log('Adjudicator analysis completed successfully.');
            } else {
                console.log('Adjudicator returned null — continuing without it.');
            }
        } catch (adjErr: any) {
            console.warn('[Adjudicator] Non-fatal error:', adjErr.message ?? adjErr);
        }

        // 4. Save to DB
        await dbOps.savePaper({
            ...paper,
            authors: paper.authors.join(', '),
            summary_zh: bilingualSummary.zh,
            summary_en: bilingualSummary.en,
            adjudicator_data: adjudicatorResult ? JSON.stringify(adjudicatorResult) : undefined
        });
        console.log('Saved to database.');

        // 5. Purge Next.js Cache
        revalidatePath('/');

        // 6. Broadcast email — ALWAYS send even if Adjudicator failed
        const subscribers = await dbOps.getAllSubscribers();
        console.log(`Sending to ${subscribers.length} subscribers...`);

        const emailResults = await Promise.allSettled(
            subscribers.map(sub =>
                sendDailySummary(
                    sub.email,
                    paper!.title,
                    bilingualSummary!.zh,
                    bilingualSummary!.en,
                    paper!.url,
                    sub.language ?? 'zh',
                    adjudicatorResult
                )
            )
        );

        const sent = emailResults.filter(r => r.status === 'fulfilled').length;
        const failed = emailResults.filter(r => r.status === 'rejected').length;
        console.log(`Email broadcast complete: ${sent} sent, ${failed} failed.`);

        return NextResponse.json({
            success: true,
            paper: paper.title,
            emailsSent: sent,
            emailsFailed: failed,
            adjudicatorRan: !!adjudicatorResult,
            summaryFallback: !bilingualSummary.zh.includes('TL;DR:') === false,
        });

    } catch (error: any) {
        console.error('Job failed with unhandled error:', error);
        return NextResponse.json({ error: 'Internal Server Error', detail: error.message }, { status: 500 });
    }
}

