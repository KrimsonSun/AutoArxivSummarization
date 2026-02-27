import { parseStringPromise } from 'xml2js';
import { subMonths, format } from 'date-fns';

export interface ArxivPaper {
    arxiv_id: string;
    title: string;
    abstract: string;
    authors: string[];
    url: string;
    published_date: string;
}

export async function fetchRandomCsPaper(): Promise<ArxivPaper | null> {
    const endDate = new Date();
    const startDate = subMonths(endDate, 1);

    const startDateStr = format(startDate, 'yyyyMMddHHmm');
    const endDateStr = format(endDate, 'yyyyMMddHHmm');

    // ArXiv API query for CS category papers from the last month
    // We fetch up to 50 papers to increase randomness
    const query = `cat:cs.*+AND+submittedDate:[${startDateStr}+TO+${endDateStr}]`;
    const url = `http://export.arxiv.org/api/query?search_query=${query}&max_results=50&sortBy=submittedDate&sortOrder=descending`;

    try {
        const response = await fetch(url);
        const xml = await response.text();
        const result = await parseStringPromise(xml);

        const entries = result.feed.entry;
        if (!entries || entries.length === 0) {
            console.warn('No papers found for the given criteria.');
            return null;
        }

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
