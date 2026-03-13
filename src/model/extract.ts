import { GoogleGenerativeAI, SchemaType } from "@google/generative-ai";
import { FineGrainedPaperMetadata } from "./types";

/**
 * Extracts fine-grained metadata from paper content using Gemini.
 * 
 * Accepts `textSource` as a pre-extracted string in any format:
 *   - Markdown (from HTML or LaTeX extractor)
 *   - JSON text (from Docling PDF extractor)  
 *   - Plain abstract (fallback)
 * 
 * No longer requires PDF download or Gemini File API upload.
 */
export async function extractFineGrainedMetadata(
    textSource: string,
    title: string,
    arxivId: string,
    publishedDate: string
): Promise<FineGrainedPaperMetadata | null> {
    if (!process.env.GEMINI_API_KEY) {
        console.error("GEMINI_API_KEY missing");
        return null;
    }

    if (!textSource || textSource.trim().length < 50) {
        console.error(`[${arxivId}] textSource is too short or empty. Skipping.`);
        return null;
    }

    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

    // Trim to avoid exceeding context limits (~100k chars max for Flash)
    const trimmedText = textSource.slice(0, 80000);

    const schema: any = {
        type: SchemaType.OBJECT,
        properties: {
            target_problem: {
                type: SchemaType.STRING,
                description: "Detailed description of the core bottleneck, gap, or problem the paper attempts to address."
            },
            proposed_solution: {
                type: SchemaType.STRING,
                description: "Detailed summary of the proposed method, algorithm, or architecture designed to solve the problem."
            },
            limitations: {
                type: SchemaType.ARRAY,
                items: { type: SchemaType.STRING },
                description: "List of explicit limitations, drawbacks, assumptions made, or future work mentioned in the paper."
            },
            datasets_used: {
                type: SchemaType.ARRAY,
                items: { type: SchemaType.STRING },
                description: "Names of any datasets used for training, evaluation, or benchmarking."
            },
            domain: {
                type: SchemaType.ARRAY,
                items: { type: SchemaType.STRING },
                description: "Relevant arXiv CS domains (e.g., cs.LG, cs.AI, cs.CV, cs.CL, cs.RO)."
            },
            is_code_available: {
                type: SchemaType.BOOLEAN,
                description: "True if a GitHub link or other code repository is mentioned."
            }
        },
        required: ["target_problem", "proposed_solution", "limitations", "datasets_used", "domain", "is_code_available"]
    };

    const model = genAI.getGenerativeModel({
        model: "gemini-1.5-flash",
        generationConfig: {
            responseMimeType: "application/json",
            responseSchema: schema,
        }
    });

    const prompt = `You are a meticulous AI research assistant. Read the following paper content and extract key structured information.
Be extremely precise with "limitations" and "target_problem".

Paper Title: ${title}
arXiv ID: ${arxivId}

--- PAPER CONTENT START ---
${trimmedText}
--- PAPER CONTENT END ---

Extract the structured metadata as JSON.`;

    try {
        const result = await model.generateContent(prompt);
        const jsonText = result.response.text();
        const data = JSON.parse(jsonText);

        return {
            arxiv_id: arxivId,
            title,
            published_date: publishedDate,
            ...data
        };
    } catch (err) {
        console.error(`[${arxivId}] Metadata LLM extraction error:`, err);
        return null;
    }
}
