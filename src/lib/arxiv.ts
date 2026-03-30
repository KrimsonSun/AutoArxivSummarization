import { parseStringPromise } from 'xml2js';
import { subMonths, subDays, format } from 'date-fns';

export interface ArxivPaper {
    arxiv_id: string;
    title: string;
    abstract: string;
    authors: string[];
    url: string;
    published_date: string;
}

export async function fetchRandomCsPaper(): Promise<ArxivPaper | null> {
    const today = new Date();

    // Range: published between 30 days ago and 5 days ago
    // (not too old, not too fresh — avoids pre-prints with uncorrected errors)
    const startDate = subMonths(today, 1);   // 30 days ago
    const endDate = subDays(today, 5);     // 5 days ago

    const startDateStr = format(startDate, 'yyyyMMddHHmm');
    const endDateStr = format(endDate, 'yyyyMMddHHmm');

    // Only Machine Learning (cs.LG) and Artificial Intelligence (cs.AI)
    const query = 'cat:cs.LG+OR+cat:cs.AI';
    const url = `http://export.arxiv.org/api/query?search_query=${query}&max_results=100&sortBy=submittedDate&sortOrder=descending`;

    try {
        const response = await fetch(url);
        const xml = await response.text();
        const result = await parseStringPromise(xml);

        const entries = result.feed.entry;
        if (!entries || entries.length === 0) {
            console.warn('No papers found for the given criteria.');
            return null;
        }

        console.log(`Found ${entries.length} papers in cs.LG/cs.AI (last 5-30 days). Picking one at random.`);

        // Pick a random entry
        const randomIndex = Math.floor(Math.random() * entries.length);
        const entry = entries[randomIndex];

        return {
            arxiv_id: entry.id[0].split('/abs/')[1],
            title: entry.title[0].replace(/\n/g, ' ').trim(),
            abstract: entry.summary[0].replace(/\n/g, ' ').trim(),
            authors: entry.author.map((a: any) => a.name[0]),
            url: entry.id[0],
            published_date: entry.published[0]
        };
    } catch (error) {
        console.error('Error fetching from arXiv:', error);
        return null;
    }
}
export async function searchPapersByQuery(query: string, maxResults: number = 10): Promise<ArxivPaper[]> {
    const encodedQuery = encodeURIComponent(query);
    const url = `http://export.arxiv.org/api/query?search_query=all:${encodedQuery}&max_results=${maxResults}&sortBy=relevance&sortOrder=descending`;

    try {
        const response = await fetch(url);
        const xml = await response.text();
        const result = await parseStringPromise(xml);

        const entries = result.feed.entry;
        if (!entries || entries.length === 0) return [];

        return entries.map((entry: any) => ({
            arxiv_id: entry.id[0].split('/abs/')[1],
            title: entry.title[0].replace(/\n/g, ' ').trim(),
            abstract: entry.summary[0].replace(/\n/g, ' ').trim(),
            authors: entry.author ? entry.author.map((a: any) => a.name[0]) : [],
            url: entry.id[0],
            published_date: entry.published[0]
        }));
    } catch (error) {
        console.error(`Error searching arXiv for "${query}":`, error);
        return [];
    }
}

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Fetches cs.LG Machine Learning papers from the last 3 years using OAI-PMH.
 * Supports incremental processing via callback to avoid giant memory/time overhead.
 */
export async function fetchDailyCsPapersIncremental(
    limit: number,
    onPageFetched: (papers: ArxivPaper[]) => Promise<void>
): Promise<number> {
    const OAI_BASE = 'http://export.arxiv.org/oai2';

    // OAI-PMH uses YYYY-MM-DD date format
    const now = new Date();
    const threeYearsAgo = new Date(now);
    threeYearsAgo.setUTCFullYear(threeYearsAgo.getUTCFullYear() - 3);
    const fromDate = threeYearsAgo.toISOString().split('T')[0]; // e.g. "2023-03-12"

    let totalCollected = 0;
    let resumptionToken: string | null = null;
    let page = 0;

    // Initial URL: ListRecords filtered by top-level set 'cs' (OAI-PMH does not have cs.LG as a set)
    // We filter to cs.LG by checking the categories field in each record.
    const initialUrl = `${OAI_BASE}?verb=ListRecords&set=cs&from=${fromDate}&metadataPrefix=arXiv`;

    while (totalCollected < limit) {
        const url = resumptionToken
            ? `${OAI_BASE}?verb=ListRecords&resumptionToken=${encodeURIComponent(resumptionToken)}`
            : initialUrl;

        page++;
        console.log(`[OAI-PMH] Fetching page ${page} (total so far: ${totalCollected})...`);

        let response: Response;
        try {
            response = await fetch(url, {
                headers: { 'User-Agent': 'AutoArxivSummarization/1.0 (research project)' }
            });
        } catch (err) {
            console.error(`[OAI-PMH] Network error on page ${page}:`, err);
            break;
        }

        if (!response.ok) {
            console.error(`[OAI-PMH] HTTP error: ${response.status} ${response.statusText}`);
            break;
        }

        const xml = await response.text();
        let parsed: any;
        try {
            parsed = await parseStringPromise(xml, { explicitArray: true });
        } catch (err) {
            console.error(`[OAI-PMH] XML parse error:`, err);
            break;
        }

        const oaiRoot = parsed?.['OAI-PMH'];
        if (!oaiRoot) break;

        const records: any[] = oaiRoot?.ListRecords?.[0]?.record ?? [];
        const pagePapers: ArxivPaper[] = [];
        
        for (const record of records) {
            if (totalCollected + pagePapers.length >= limit) break;
            try {
                const metadata = record?.metadata?.[0]?.arXiv?.[0];
                if (!metadata) continue;

                const arxivIdRaw: string = metadata?.id?.[0] ?? '';
                const arxiv_id = arxivIdRaw.trim();
                const categories: string = metadata?.categories?.[0] ?? '';
                if (!categories.includes('cs.LG')) continue;

                const title: string = (metadata?.title?.[0] ?? '').replace(/\s+/g, ' ').trim();
                const abstract: string = (metadata?.abstract?.[0] ?? '').replace(/\s+/g, ' ').trim();
                const published_date: string = metadata?.created?.[0] ?? '';

                const authorList = metadata?.authors?.[0]?.author ?? [];
                const authors: string[] = authorList.map((a: any) => {
                    const forenames = a?.forenames?.[0] ?? '';
                    const keyname = a?.keyname?.[0] ?? '';
                    return `${forenames} ${keyname}`.trim();
                });

                pagePapers.push({ arxiv_id, title, abstract, authors, url: `https://arxiv.org/abs/${arxiv_id}`, published_date });
            } catch { }
        }

        if (pagePapers.length > 0) {
            totalCollected += pagePapers.length;
            await onPageFetched(pagePapers);
        }

        const tokenNode = oaiRoot?.ListRecords?.[0]?.resumptionToken?.[0];
        resumptionToken = typeof tokenNode === 'string' ? tokenNode : tokenNode?._ ?? null;

        if (!resumptionToken) break;
        await sleep(20000);
    }

    return totalCollected;
}
