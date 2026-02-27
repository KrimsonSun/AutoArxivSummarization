import { GoogleGenerativeAI } from '@google/generative-ai';

export interface BilingualSummary {
    zh: string;
    en: string;
}

/**
 * Download arXiv PDF and return as base64 string.
 * Falls back to null if download fails.
 */
async function downloadPdfAsBase64(arxivId: string): Promise<string | null> {
    const pdfUrl = `https://arxiv.org/pdf/${arxivId}`;
    try {
        console.log(`Downloading PDF from: ${pdfUrl}`);
        const response = await fetch(pdfUrl, {
            headers: { 'User-Agent': 'AutoArxivBot/1.0 (research summarizer)' },
            signal: AbortSignal.timeout(30_000), // 30s timeout
        });

        if (!response.ok) {
            console.warn(`PDF download failed: HTTP ${response.status}`);
            return null;
        }

        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('pdf')) {
            console.warn(`Unexpected content-type: ${contentType}`);
            return null;
        }

        const buffer = await response.arrayBuffer();
        const sizeKB = Math.round(buffer.byteLength / 1024);
        console.log(`PDF downloaded: ${sizeKB} KB`);

        // Gemini inline data limit: 20 MB
        if (buffer.byteLength > 20 * 1024 * 1024) {
            console.warn('PDF too large (> 20 MB), falling back to abstract.');
            return null;
        }

        return Buffer.from(buffer).toString('base64');
    } catch (err) {
        console.error('Failed to download PDF:', err);
        return null;
    }
}

/**
 * Summarize a paper using Gemini.
 * If arxivId is provided, downloads the FULL PDF and passes it to Gemini.
 * Falls back to abstract-only summarization if PDF download fails.
 */
export async function summarizePaper(
    title: string,
    abstract: string,
    arxivId?: string
): Promise<BilingualSummary | null> {
    if (!process.env.GEMINI_API_KEY) {
        console.error('Missing GEMINI_API_KEY environment variable');
        return null;
    }

    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
    const model = genAI.getGenerativeModel({
        model: 'gemini-2.5-flash',
        // No JSON mode — we use delimiter tags to avoid JSON escaping issues with long academic text
    });

    // Try full PDF first
    const pdfBase64 = arxivId ? await downloadPdfAsBase64(arxivId) : null;
    const usingFullPdf = !!pdfBase64;

    const prompt = usingFullPdf
        ? `You are an expert academic researcher. You have been given the FULL PDF of a Computer Science research paper.

Read the entire paper — introduction, methodology, experiments, results, conclusion.

Provide a thorough summary covering:
1. The core problem being solved
2. The proposed approach / key innovation
3. Main results and their significance
4. Broader impact / takeaway

Write BOTH a Chinese and an English summary. Use EXACTLY these delimiter tags and nothing else outside them:

<ZH>
[3-5 paragraph Chinese summary in Tech Blog style — informative and engaging]
</ZH>

<EN>
[3-5 paragraph English summary — professional and academic-friendly]
</EN>

Paper title: ${title}`
        : `You are an expert academic researcher. Summarize this CS paper concisely.

Use EXACTLY these delimiter tags:

<ZH>
[Chinese summary in Tech Blog style]
</ZH>

<EN>
[English professional summary]
</EN>

Paper Title: ${title}
Abstract: ${abstract}`;

    const parts: any[] = [{ text: prompt }];

    if (pdfBase64) {
        // Insert PDF before the prompt text so Gemini reads the file first
        parts.unshift({
            inlineData: {
                mimeType: 'application/pdf',
                data: pdfBase64,
            },
        });
        console.log('Sending full PDF to Gemini for deep analysis...');
    } else {
        console.log('Sending abstract to Gemini (PDF unavailable)...');
    }

    try {
        const result = await model.generateContent(parts);
        const response = await result.response;
        const text = response.text().trim();

        // Parse delimiter-based response: <ZH>...</ZH> and <EN>...</EN>
        const zhMatch = text.match(/<ZH>([\s\S]*?)<\/ZH>/);
        const enMatch = text.match(/<EN>([\s\S]*?)<\/EN>/);

        if (zhMatch && enMatch) {
            const summary: BilingualSummary = {
                zh: zhMatch[1].trim(),
                en: enMatch[1].trim(),
            };
            console.log(`Summary generated (${usingFullPdf ? 'full PDF' : 'abstract only'})`);
            return summary;
        }

        // Fallback: try JSON parsing (for any legacy responses)
        try {
            const parsed = JSON.parse(text) as BilingualSummary;
            console.log(`Summary parsed as JSON fallback.`);
            return parsed;
        } catch {
            console.error('All parsing strategies failed. Raw output (first 400 chars):', text.slice(0, 400));
            return null;
        }
    } catch (error: any) {
        console.error('Error calling Gemini API:', error.message ?? error);
        return null;
    }
}
