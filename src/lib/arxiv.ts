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

/**
 * Fetches the latest CS papers (up to `limit`).
 * Respects arXiv rate limits by batching requests.
 */
export async function fetchDailyCsPapers(limit: number = 1000): Promise<ArxivPaper[]> {
    const query = 'cat:cs.LG+OR+cat:cs.AI+OR+cat:cs.CV+OR+cat:cs.CL';
    const batchSize = 100;
    let allPapers: ArxivPaper[] = [];

    for (let start = 0; start < limit; start += batchSize) {
        const url = `http://export.arxiv.org/api/query?search_query=${query}&start=${start}&max_results=${Math.min(batchSize, limit - start)}&sortBy=submittedDate&sortOrder=descending`;
        console.log(`Fetching arXiv papers start=${start}...`);
        
        try {
            const response = await fetch(url);
            if (!response.ok) {
                console.error(`arXiv API error: ${response.statusText}`);
                break;
            }
            const xml = await response.text();
            const result = await parseStringPromise(xml);
            const entries = result.feed.entry;

            if (!entries || entries.length === 0) {
                console.log('No more papers found.');
                break;
            }

            const parsedPapers = entries.map((entry: any) => ({
                arxiv_id: entry.id[0].split('/abs/')[1],
                title: entry.title[0].replace(/\n/g, ' ').trim(),
                abstract: entry.summary[0].replace(/\n/g, ' ').trim(),
                authors: entry.author ? entry.author.map((a: any) => a.name[0]) : [],
                url: entry.id[0],
                published_date: entry.published[0]
            }));

            allPapers = allPapers.concat(parsedPapers);

            if (entries.length < batchSize) break;

            if (start + batchSize < limit) {
                await new Promise(resolve => setTimeout(resolve, 3100)); // 3.1s delay
            }
        } catch (error) {
            console.error('Error fetching daily arXiv papers:', error);
            break;
        }
    }

    return allPapers;
}
