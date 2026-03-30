import { Pinecone } from '@pinecone-database/pinecone';
import { FineGrainedPaperMetadata } from './types';

// Uses a self-hosted Nomic Embedding Service instance instead of Google
export async function embedText(text: string): Promise<number[]> {
    const port = process.env.EMBED_SERVICE_PORT || "8000";
    const host = process.env.EMBED_SERVICE_HOST || "http://localhost";
    const url = `${host}:${port}/embed`;

    // Nomic requires specific task prefixes - we'll let the microservice handle it
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, task_type: "search_document" })
    });

    if (!response.ok) {
        throw new Error(`Embedding service failed: ${response.statusText}`);
    }

    const result = await response.json();
    return result.embedding; // The microservice handles the 512-dim slicing
}

// Ensure PINECONE_API_KEY and PINECONE_INDEX are configured in your .env
export async function getPineconeIndex() {
    const pc = new Pinecone({ apiKey: process.env.PINECONE_API_KEY! });
    return pc.index(process.env.PINECONE_INDEX!);
}

/**
 * Checks if any chunks for a specific arxiv_id already exist in the index.
 */
export async function checkPaperExists(arxivId: string): Promise<boolean> {
    const pcIndex = await getPineconeIndex();
    // Query with a metadata filter. We use a dummy zero vector since we only care about the filter.
    const queryResponse = await pcIndex.query({
        vector: Array(512).fill(0),
        topK: 1,
        filter: { arxiv_id: { '$eq': arxivId } },
        includeMetadata: false
    });
    return queryResponse.matches.length > 0;
}

/**
 * Encodes the paper's SOLUTION and upserts it into Pinecone.
 * This represents "what this paper is capable of solving".
 */
export async function upsertPaperSolution(metadata: FineGrainedPaperMetadata) {
    const pcIndex = await getPineconeIndex();

    // Combine problem and solution to provide broader semantic context for matching
    const textToEmbed = `The problem focuses on: ${metadata.target_problem}. The presented solution is: ${metadata.proposed_solution}`;
    const values = await embedText(textToEmbed);

    await pcIndex.upsert({
        records: [{
            id: `${metadata.arxiv_id}_sol`,
            values,
            metadata: {
                arxiv_id: metadata.arxiv_id,
                title: metadata.title,
                published_date: metadata.published_date,
                domain: metadata.domain || [],
                limitations: metadata.limitations || [],
                target_problem: metadata.target_problem || "",
                is_code_available: !!metadata.is_code_available
            }
        }]
    });
}

/**
 * CORE LOGIC: Find papers whose "Solution Text" matches the given Limitation.
 */
export async function findSolutionsForLimitation(limitationText: string, topK: number = 3) {
    const pcIndex = await getPineconeIndex();

    // Formulate a query embedding as if we are asking to solve this limitation
    const queryValues = await embedText(`Solution addressing: ${limitationText}`);

    const queryResponse = await pcIndex.query({
        vector: queryValues,
        topK,
        includeMetadata: true,
        // (Optional) Filter by specific domain
        filter: {
            domain: { "$in": ["cs.LG"] }
        }
    });

    return queryResponse.matches;
}

/**
 * Formats and cleans the paper text to remove noise like authors, affiliations, and emails.
 * It looks for "Abstract" or "Introduction" to start, and optionally scrubs known author names.
 */
function cleanPaperText(text: string, authors: string[] = []): string {
    const markers = [
        /abstract/i, 
        /# abstract/i, 
        /## abstract/i, 
        /introduction/i, 
        /# introduction/i, 
        /## introduction/i,
        /\*\*abstract\*\*/i,
        /\*\*introduction\*\*/i
    ];
    
    let startIndex = 0;
    
    // 1. Try to find the first major section start
    for (const marker of markers) {
        const match = text.match(marker);
        if (match && match.index !== undefined) {
            // If the match is in the first 20% of the document, it's likely the header
            if (match.index < text.length * 0.2) {
                startIndex = match.index;
                break;
            }
        }
    }
    
    let cleaned = text.slice(startIndex).trim();

    // 2. Remove known author names if they appear at the very beginning of the cleaned text
    // (sometimes 'Abstract' tag comes after authors in some conversions)
    if (authors.length > 0) {
        for (const author of authors) {
            if (author.length < 3) continue; // skip too short names for safety
            const escaped = author.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const authorRegex = new RegExp(`^\\s*${escaped}\\s*`, 'i');
            cleaned = cleaned.replace(authorRegex, '');
        }
    }

    // 3. Scrub common email patterns and affiliation noise from the first 500 chars 
    // if we are still at the start of the doc
    if (startIndex === 0 || cleaned.length > 0) {
        const initialSegment = cleaned.slice(0, 1000);
        const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
        const cleanedSegment = initialSegment.replace(emailRegex, '[EMAIL]');
        cleaned = cleanedSegment + cleaned.slice(1000);
    }
    
    return cleaned.trim();
}

/**
 * Safe string slicing that doesn't break surrogate pairs.
 */
function safeSlice(str: string, start: number, end: number): string {
    // Array.from is surrogate-aware but potentially slow for huge strings.
    // For 1000-char chunks, it's perfectly fine.
    return Array.from(str).slice(start, end).join('');
}

/**
 * Removes lone surrogates and other non-standard Unicode that cause serialization errors.
 * This version uses TextEncoder/TextDecoder to guarantee valid UTF-8.
 */
function scrubInvalidSurrogates(str: string): string {
    if (!str) return "";
    
    // 1. Force round-trip through TextEncoder with default error handling (lossy)
    // In Node.js, TextEncoder/Decoder naturally handle malformed surrogates by replacing them.
    try {
        const encoder = new TextEncoder();
        const decoder = new TextDecoder("utf-8", { fatal: false });
        const encoded = encoder.encode(str);
        const cleaned = decoder.decode(encoded);
        
        // 2. Normalize and remove any residual lone surrogates just in case
        return cleaned.normalize('NFC').replace(/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/g, '');
    } catch (err) {
        // Ultimate fallback: regex only
        return str.replace(/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/g, '');
    }
}

/**
 * Full-text embedding function with advanced chunking.
 * - 10% Overlap
 * - Text Cleaning
 * - Section / Subtitle metadata tracking
 */
export async function upsertFullPaperChunks(paper: any, rawText: string) {
    const pcIndex = await getPineconeIndex();
    // Scrub the entire text first
    const sanitizedRawText = scrubInvalidSurrogates(rawText);
    const cleanText = cleanPaperText(sanitizedRawText, paper.authors);

    // Using ~1000 "characters" (surrogate-aware)
    const chunkSize = 1000;
    const overlap = 100;
    const records = [];

    // Convert to array for surrogate-aware indexing
    const textChars = Array.from(cleanText);
    const totalChars = textChars.length;

    let currentSection = "Introduction";
    let chunkIndex = 0;
    let cursor = 0;

    while (cursor < totalChars) {
        let end = Math.min(cursor + chunkSize, totalChars);
        const chunkStr = textChars.slice(cursor, end).join('');

        // Update current section if we hit a Markdown header in this chunk
        const headerMatch = chunkStr.match(/##\s+(.*)/);
        if (headerMatch) {
            currentSection = headerMatch[1].trim();
        }

        const textToEmbed = `Title: ${paper.title}\nSection: ${currentSection}\nContent: ${chunkStr}`;
        
        try {
            const values = await embedText(textToEmbed);
            
            records.push({
                id: `${paper.arxiv_id}_chunk_${chunkIndex}`,
                values,
                metadata: {
                    arxiv_id: paper.arxiv_id,
                    title: paper.title,
                    subtitle: currentSection,
                    published_date: paper.published_date,
                    domain: ["cs.LG"],
                    chunk_index: chunkIndex,
                    chunk_version: "v2", 
                    snippet: chunkStr.slice(0, 500)
                }
            });
            
            chunkIndex++;
            cursor += (chunkSize - overlap);
            if (overlap >= chunkSize) break;

            await new Promise(resolve => setTimeout(resolve, 50));
        } catch (err) {
            console.error(`Failed to embed chunk ${chunkIndex} for ${paper.arxiv_id}`, err);
            cursor += chunkSize;
        }
    }

    // Upsert in batches of 100
    for (let i = 0; i < records.length; i += 100) {
        const batch = records.slice(i, i + 100);
        await pcIndex.upsert({ records: batch });
    }
}
