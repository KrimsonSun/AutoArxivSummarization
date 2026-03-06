import { GoogleGenerativeAI, Schema, Type } from "@google/generative-ai";
import { FineGrainedPaperMetadata } from "./types";

export async function extractFineGrainedMetadata(
    markdown: string,
    title: string,
    arxivId: string,
    publishedDate: string
): Promise<FineGrainedPaperMetadata | null> {
    if (!process.env.GEMINI_API_KEY) {
        console.error("GEMINI_API_KEY missing");
        return null;
    }

    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

    // Define strict schema to enforce JSON output matching our FineGrainedPaperMetadata
    const schema: Schema = {
        type: Type.OBJECT,
        properties: {
            target_problem: { type: Type.STRING, description: "Detailed description of the core bottleneck, gap, or problem the paper attempts to address." },
            proposed_solution: { type: Type.STRING, description: "Detailed summary of the proposed method, algorithm, or architecture designed to solve the problem." },
            limitations: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description: "List of explicit limitations, drawbacks, assumptions made, or future work mentioned in the paper text."
            },
            datasets_used: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description: "Names of any datasets utilized for training, evaluation, or benchmarking."
            },
            domain: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description: "Relevant computer science domains (e.g., cs.LG, cs.AI, cs.CV, cs.CL, cs.RO)."
            },
            is_code_available: { type: Type.BOOLEAN, description: "True if a GitHub link or other code repository is mentioned." }
        },
        required: ["target_problem", "proposed_solution", "limitations", "datasets_used", "domain", "is_code_available"]
    };

    const model = genAI.getGenerativeModel({
        model: "gemini-2.5-flash",
        generationConfig: {
            responseMimeType: "application/json",
            responseSchema: schema,
        }
    });

    const prompt = `
    You are a meticulous AI research assistant. Read the following paper text (markdown format) and extract key structured information.
    Be extremely precise with "limitations" and "target_problem".
    
    Paper Title: ${title}
    
    Paper Text:
    ${markdown}

    Extract the structured metadata as JSON.
  `;

    try {
        const result = await model.generateContent(prompt);
        const jsonText = result.response.text();
        const data = JSON.parse(jsonText);

        return {
            arxiv_id: arxivId,
            title: title,
            published_date: publishedDate,
            ...data
        };
    } catch (err) {
        console.error("Metadata LLM extraction error:", err);
        return null;
    }
}
