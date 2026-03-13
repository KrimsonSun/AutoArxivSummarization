import { Pinecone } from '@pinecone-database/pinecone';
import { GoogleGenerativeAI } from '@google/generative-ai';
import { FineGrainedPaperMetadata } from './types';

// Utility to create embeddings via Gemini API (very cost effective)
export async function embedText(text: string): Promise<number[]> {
    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
    // text-embedding-004 is current standard Gemini embedding model
    const model = genAI.getGenerativeModel({ model: "text-embedding-004" });
    const result = await model.embedContent(text);
    return result.embedding.values;
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
