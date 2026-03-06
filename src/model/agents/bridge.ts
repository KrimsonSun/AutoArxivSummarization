import axios from 'axios';
import { BridgePlan, BridgeEvidence, AttackSchema } from './types.ts';
import { GoogleGenerativeAI, Schema, SchemaType } from "@google/generative-ai";

interface S2Paper {
    paperId: string;
    title: string;
    abstract: string;
    year: number;
    url: string;
    authors: { name: string }[];
    citations?: { paperId: string; title: string; abstract: string }[];
    references?: { paperId: string; title: string; abstract: string }[];
}

/**
 * Helper: Fetches initial papers based on testable question,
 * then tries to fetch their citations/references (the "Graph Expansion").
 */
async function fetchExpandedCandidates(query: string): Promise<S2Paper[]> {
    try {
        const headers = process.env.SEMANTIC_SCHOLAR_API_KEY
            ? { "x-api-key": process.env.SEMANTIC_SCHOLAR_API_KEY }
            : {};

        // 1. Initial keyword search
        const response = await axios.get("https://api.semanticscholar.org/graph/v1/paper/search", {
            headers,
            params: { query, limit: 3, fields: "paperId,title,abstract,year,authors,url" }
        });

        const candidates: S2Paper[] = response.data.data || [];
        if (candidates.length === 0) return [];

        // 2. Citation Graph Expansion (Fetching 1 hop citations/references for top 2 candidates to avoid rate limits)
        const expandedList: S2Paper[] = [...candidates];

        // IF WE HAVE NO API KEY, SKIP GRAPH EXPANSION TO AVOID INSTANT 429 RATE LIMITS
        if (process.env.SEMANTIC_SCHOLAR_API_KEY) {
            for (const paper of candidates.slice(0, 2)) {
                try {
                    const detailRes = await axios.get(`https://api.semanticscholar.org/graph/v1/paper/${paper.paperId}`, {
                        headers,
                        params: { fields: "citations.paperId,citations.title,citations.abstract,references.paperId,references.title,references.abstract" }
                    });

                    const details = detailRes.data;
                    if (details.citations) {
                        details.citations.slice(0, 2).forEach((c: any) => expandedList.push({ ...c, url: `https://semanticscholar.org/paper/${c.paperId}`, authors: [], year: 0 }));
                    }
                    if (details.references) {
                        details.references.slice(0, 2).forEach((r: any) => expandedList.push({ ...r, url: `https://semanticscholar.org/paper/${r.paperId}`, authors: [], year: 0 }));
                    }
                    // Be nice to S2 API
                    await new Promise(r => setTimeout(r, 1000));
                } catch (e) { /* Ignore individual graph fetch failures */ }
            }
        } else {
            console.log("   [Agent C] No API Key found, skipping 2nd hop graph expansion to respect rate limits.");
        }

        // De-duplicate and filter out papers without abstracts
        const uniqueMap = new Map();
        expandedList.forEach(p => {
            if (p.abstract && p.title && !uniqueMap.has(p.paperId)) {
                uniqueMap.set(p.paperId, p);
            }
        });

        return Array.from(uniqueMap.values());
    } catch (error: any) {
        console.error("[Agent C Graph Fetch Error] :", error.response?.status || error.message);
        return [];
    }
}

/**
 * Agent C (The Bridge)
 * Uses Semantic Scholar Graph API and an LLM to identify specific EVIDENCE level chunks.
 */
export async function agentC_BridgeAndSolve(attack: AttackSchema): Promise<BridgePlan> {
    console.log(`\n[Agent C] Bridging Attack: [${attack.attack_type}] -> ${attack.testable_question}`);

    // 1. Semantic Scholar Citation Graph Retrieval
    const candidates = await fetchExpandedCandidates(attack.testable_question);

    if (candidates.length === 0) {
        return { target_attack_question: attack.testable_question, found_solutions: [] };
    }

    // 2. Evidence-level Tagging & Reranking using LLM
    // We feed the candidates to Gemini to extract the precise evidence chunk satisfying the attack's requirements.
    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);

    const schema: Schema = {
        type: SchemaType.OBJECT,
        properties: {
            found_solutions: {
                type: SchemaType.ARRAY,
                items: {
                    type: SchemaType.OBJECT,
                    properties: {
                        paper_id: { type: SchemaType.STRING },
                        evidence_chunk: { type: SchemaType.STRING, description: "Exact quote or precise summary of the chunk proving the solution" },
                        evidence_type: { type: SchemaType.STRING, enum: ["experiment", "theorem", "ablation", "dataset", "limitation", "negative result"] },
                        satisfies_attack: { type: SchemaType.BOOLEAN, description: "True if this completely handles the missing evidence described by Agent B" }
                    },
                    required: ["paper_id", "evidence_chunk", "evidence_type", "satisfies_attack"]
                }
            }
        },
        required: ["found_solutions"]
    };

    const model = genAI.getGenerativeModel({
        model: "gemini-2.5-flash",
        generationConfig: { responseMimeType: "application/json", responseSchema: schema }
    });

    const prompt = `
    You are an Evidence Reranker. Agent B raised a critical attack on a paper.
    Your goal is to scan the provided candidate abstracts and extract specific EVIDENCE CHUNKS 
    that answer the Testable Question and provide the Evidence Needed.
    Only include papers that provide genuine evidence, do not force a match.

    ATTACK CONTEXT:
    Testable Question: ${attack.testable_question}
    Evidence Needed: ${attack.evidence_needed}
    Missing Variable: ${attack.missing_variable}

    CANDIDATE PAPERS:
    ${JSON.stringify(candidates.map(c => ({ id: c.paperId, title: c.title, abstract: c.abstract })), null, 2)}
  `;

    try {
        const result = await model.generateContent(prompt);
        const parsed = JSON.parse(result.response.text());

        // Map LLM output back to full paper details
        const solutions: BridgeEvidence[] = parsed.found_solutions.map((sol: any) => {
            const match = candidates.find(c => c.paperId === sol.paper_id);
            return {
                paper_id: sol.paper_id,
                title: match?.title || "Unknown Title",
                url: match?.url || `https://semanticscholar.org/paper/${sol.paper_id}`,
                year: match?.year || 0,
                authors: match?.authors?.map(a => a.name) || [],
                evidence_chunk: sol.evidence_chunk,
                evidence_type: sol.evidence_type,
                satisfies_attack: sol.satisfies_attack
            };
        });

        return {
            target_attack_question: attack.testable_question,
            found_solutions: solutions.filter(s => s.satisfies_attack) // Only return strong matches
        };

    } catch (error) {
        console.error("[Agent C Rerank Error] :", error);
        return { target_attack_question: attack.testable_question, found_solutions: [] };
    }
}
