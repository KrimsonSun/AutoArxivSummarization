import { GoogleGenerativeAI } from '@google/generative-ai';

export interface BilingualSummary {
    zh: string;
    en: string;
    limitations?: string; // Stored in English for better search query generation
    searchQueries?: string[]; // Recommended search terms to find papers solving limitations
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
        ? `You are an expert academic researcher analyzing a Computer Science paper (ML/AI domain).
You have been given the FULL PDF. Read the entire paper carefully.

Output EXACTLY in the following structure — no extra text outside the <ZH> and <EN> tags:

<ZH>
TL;DR: [一句话：用什么方法实现了什么目标，效果提升多少（如有具体数字请引用）]

SECTION: 研究方法
[详细描述本文提出的核心方法或模型架构]

SECTION: 数据来源
[描述使用的数据集、训练数据来源、数据规模等；若PDF未提及则写"本文未详细说明数据来源"]

SECTION: 效果表现
[列出关键实验结果、基准测试得分、与其他方法的对比]

SECTION: [自选标题，如"核心创新点"、"局限性与未来方向"、"实际应用场景"等，选最能补充上述内容的角度]
[对应内容]
</ZH>

<LIMITATIONS>
[Concisely list 2-3 specific technical limitations or future work items mentioned in the paper. English only.]
</LIMITATIONS>

<QUERIES>
[Provide 3-5 specific search queries (keywords/phrases) that would help find papers resolving the limitations above. One query per line.]
</QUERIES>

<EN>
TL;DR: [One sentence: what method achieves what goal, with quantified improvement if available]

SECTION: Research Methodology
[Describe the proposed method, model architecture, or algorithmic approach]

SECTION: Data Sources
[Describe datasets used, training data, scale; write "Not detailed in paper" if unavailable]

SECTION: Performance
[Key experimental results, benchmark scores, comparison with baselines]

SECTION: [Choose the most relevant title: e.g. "Key Innovations", "Limitations & Future Work", "Practical Applications"]
[Corresponding content]
</EN>

Paper title: ${title}`
        : `You are an expert academic researcher. Analyze this CS/ML paper from its title and abstract.

Output EXACTLY in this structure:

<ZH>
TL;DR: [一句话总结]

SECTION: 研究方法
[内容，若摘要信息不足则如实说明]

SECTION: 数据来源
[内容]

SECTION: 效果表现
[内容]
</ZH>

<EN>
TL;DR: [one sentence summary]

SECTION: Research Methodology
[content]

SECTION: Data Sources
[content]

SECTION: Performance
[content]
</EN>

<LIMITATIONS>
[Limitations based on abstract]
</LIMITATIONS>

<QUERIES>
[Search queries based on abstract]
</QUERIES>

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
        const limMatch = text.match(/<LIMITATIONS>([\s\S]*?)<\/LIMITATIONS>/);
        const queryMatch = text.match(/<QUERIES>([\s\S]*?)<\/QUERIES>/);

        if (zhMatch && enMatch) {
            const summary: BilingualSummary = {
                zh: zhMatch[1].trim(),
                en: enMatch[1].trim(),
                limitations: limMatch ? limMatch[1].trim() : undefined,
                searchQueries: queryMatch ? queryMatch[1].trim().split('\n').map(q => q.trim()).filter(q => q.length > 0) : undefined,
            };
            console.log(`Summary generated (${usingFullPdf ? 'full PDF' : 'abstract only'}) with ${summary.searchQueries?.length || 0} search queries.`);
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
