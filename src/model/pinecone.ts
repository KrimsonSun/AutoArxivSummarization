import { Pinecone } from '@pinecone-database/pinecone';
import { GoogleGenerativeAI } from '@google/generative-ai';
import { FineGrainedPaperMetadata } from './types';

// Utility to create embeddings via Gemini API (very cost effective)
export async function embedText(text: string): Promise<number[]> {
    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
    // Using gemini-embedding-001 which natively outputs 768 dimensions for Pinecone
    const model = genAI.getGenerativeModel({ model: "gemini-embedding-001" });
    const result = await model.embedContent(text);
    return result.embedding.values.slice(0, 768);
}

// Ensure PINECONE_API_KEY and PINECONE_INDEX are configured in your .env
export async function getPineconeIndex() {
    const pc = new Pinecone({ apiKey: process.env.PINECONE_API_KEY! });
    return pc.index(process.env.PINECONE_INDEX!);
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
 * Formats and cleans the paper text to remove noise like authors and affiliations.
 * It looks for "Abstract" or "Introduction" to start.
 */
function cleanPaperText(text: string): string {
    const markers = [/abstract/i, /# abstract/i, /## abstract/i, /introduction/i, /# introduction/i, /## introduction/i];
    let startIndex = 0;
    
    for (const marker of markers) {
        const match = text.match(marker);
        if (match && match.index !== undefined) {
            startIndex = match.index;
            break;
        }
    }
    
    return text.slice(startIndex).trim();
}

/**
 * Full-text embedding function with advanced chunking.
 * - 10% Overlap
 * - Text Cleaning
 * - Section / Subtitle metadata tracking
 */
export async function upsertFullPaperChunks(paper: any, rawText: string) {
    const pcIndex = await getPineconeIndex();
    const cleanText = cleanPaperText(rawText);

    // Using ~1000 chars for roughly 256 tokens.
    const chunkSize = 1000;
    const overlap = 100;
    const records = [];

    let currentSection = "Introduction";
    let chunkIndex = 0;
    let cursor = 0;

    while (cursor < cleanText.length) {
        let end = Math.min(cursor + chunkSize, cleanText.length);
        const chunkStr = cleanText.slice(cursor, end);

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
                    chunk_version: "v2", // New version to distinguish from old 8000-char chunks
                    snippet: chunkStr.slice(0, 500)
                }
            });
            
            chunkIndex++;
            
            // Move cursor forward by (chunkSize - overlap)
            cursor += (chunkSize - overlap);
            
            // Safety break if overlap makes cursor stuck
            if (overlap >= chunkSize) break;

            // Rate limit respect
            await new Promise(resolve => setTimeout(resolve, 500));
        } catch (err) {
            console.error(`Failed to embed chunk ${chunkIndex} for ${paper.arxiv_id}`, err);
            cursor += chunkSize; // Skip ahead on error
        }
    }

    // Upsert in batches of 100
    for (let i = 0; i < records.length; i += 100) {
        const batch = records.slice(i, i + 100);
        await pcIndex.upsert({ records: batch });
    }
}
