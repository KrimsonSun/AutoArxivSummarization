import { GoogleGenerativeAI, SchemaType } from '@google/generative-ai';
import { findSolutionsForLimitation } from '../src/model/pinecone';
import { AdjudicatorFinalResult, AdjudicatorGraph, AdjudicatorMismatch, AdjudicatorSolutionInput, PineconeReference } from './schemas';

// Define the expected output structure using Gemini's native Schema format
const matchSchema = {
    type: SchemaType.OBJECT,
    properties: {
        graph: {
            type: SchemaType.OBJECT,
            properties: {
                premises: {
                    type: SchemaType.ARRAY,
                    items: {
                        type: SchemaType.OBJECT,
                        properties: {
                            span: { type: SchemaType.STRING },
                            description: { type: SchemaType.STRING, description: 'Chinese description of this node' },
                            description_en: { type: SchemaType.STRING, description: 'English description of this node' }
                        },
                        required: ["span", "description", "description_en"]
                    }
                },
                processes: {
                    type: SchemaType.ARRAY,
                    items: {
                        type: SchemaType.OBJECT,
                        properties: {
                            span: { type: SchemaType.STRING },
                            description: { type: SchemaType.STRING, description: 'Chinese description of this node' },
                            description_en: { type: SchemaType.STRING, description: 'English description of this node' }
                        },
                        required: ["span", "description", "description_en"]
                    }
                },
                conclusions: {
                    type: SchemaType.ARRAY,
                    items: {
                        type: SchemaType.OBJECT,
                        properties: {
                            span: { type: SchemaType.STRING },
                            description: { type: SchemaType.STRING, description: 'Chinese description of this node' },
                            description_en: { type: SchemaType.STRING, description: 'English description of this node' }
                        },
                        required: ["span", "description", "description_en"]
                    }
                }
            },
            required: ["premises", "processes", "conclusions"]
        },
        mismatch: {
            type: SchemaType.OBJECT,
            properties: {
                mismatch_type: { 
                    type: SchemaType.STRING, 
                    enum: [
                        'Dimensional Mismatch', 
                        'Domain Mismatch', 
                        'Resource Mismatch', 
                        'Metric Mismatch', 
                        'Causality Leap',
                        'Assumption Constraint'
                    ] 
                },
                severity: { type: SchemaType.STRING, enum: ['Critical', 'Major'] },
                broken_edge: { type: SchemaType.STRING, description: 'e.g., "Premise -> Conclusion"' },
                reasoning: { type: SchemaType.STRING, description: 'Detailed explanation of logical flaw in Chinese.' },
                reasoning_en: { type: SchemaType.STRING, description: 'Detailed explanation of the same logical flaw in English.' },
                testable_question: { type: SchemaType.STRING, description: 'A question to challenge the mismatch (English)' }
            },
            required: ["mismatch_type", "severity", "broken_edge", "reasoning", "reasoning_en", "testable_question"]
        },
        solutions: {
            type: SchemaType.ARRAY,
            items: {
                type: SchemaType.OBJECT,
                properties: {
                    direction: { type: SchemaType.STRING, description: 'Direction label in Chinese, e.g. "理论层面修补"' },
                    direction_en: { type: SchemaType.STRING, description: 'Direction label in English, e.g. "Theoretical Patch"' },
                    proposed_method: { type: SchemaType.STRING, description: 'Detailed solution description in Chinese.' },
                    proposed_method_en: { type: SchemaType.STRING, description: 'Detailed solution description in English.' },
                    pinecone_query: { type: SchemaType.STRING, description: 'A robust English search string to find related papers in an academic vector database. Use English academic keywords only.' }
                },
                required: ["direction", "direction_en", "proposed_method", "proposed_method_en", "pinecone_query"]
            }
        }
    },
    required: ["graph", "mismatch", "solutions"]
};

export async function runAdjudicator(title: string, abstract: string, fullText: string = ""): Promise<AdjudicatorFinalResult | null> {
    try {
        const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
        if (!apiKey) throw new Error("GEMINI_API_KEY is not defined.");

        // We use gemini-3.1-pro-preview for complex logical reasoning
        const genAI = new GoogleGenerativeAI(apiKey);
        const model = genAI.getGenerativeModel({
            model: "gemini-3.1-pro-preview",
            generationConfig: {
                responseMimeType: "application/json",
                responseSchema: matchSchema as any
            }
        });

        // Retry helper: exponential backoff for 503 Service Unavailable
        async function generateWithRetry(parts: any, maxRetries = 3): Promise<any> {
            for (let attempt = 1; attempt <= maxRetries; attempt++) {
                try {
                    return await model.generateContent(parts);
                } catch (err: any) {
                    const is503 = err?.status === 503 || err?.message?.includes('503');
                    if (is503 && attempt < maxRetries) {
                        const waitMs = attempt * 30000; // 30s, 60s
                        console.warn(`[Adjudicator] Gemini 503 on attempt ${attempt}. Retrying in ${waitMs / 1000}s...`);
                        await new Promise(r => setTimeout(r, waitMs));
                    } else {
                        throw err;
                    }
                }
            }
        }

        const prompt = `你是一个极为严谨的计算机科学(机器学习)领域的学术推演官(Adjudicator)。你需要对以下这篇论文进行深度解构和文献匹配。

CRITICAL REQUIREMENT: You MUST output BILINGUAL content. Every field that describes analysis content must have BOTH a Chinese version AND an English version. Specifically:
- graph nodes: provide both "description" (Chinese) and "description_en" (English) 
- mismatch: provide both "reasoning" (Chinese) and "reasoning_en" (English)
- solutions: provide both "direction" + "proposed_method" (Chinese) AND "direction_en" + "proposed_method_en" (English)
- pinecone_query: ALWAYS in English only (academic keywords)

目标：
1. **图结构化提取 (Graph)**：强制将论文解构为3个节点：物理前提/假设 (Premises)、工程/算法过程 (Processes)、最终宣称的结论/效果 (Conclusions)。每个节点提供中文description和英文description_en。
2. **找出逻辑断裂 (Mismatch)**：在这条 "前提->过程->结论" 逻辑链条中找出一处最严重、最虚浮的逻辑断裂点。提供中文reasoning和英文reasoning_en。
3. **针对局限性的破局方案 (Solutions)**：给出3个不同技术方向的改进方案。每个方案提供：
   - direction (中文方向标签), direction_en (English direction label)
   - proposed_method (中文详细描述), proposed_method_en (English detailed description)
   - pinecone_query (英文学术关键词，用于向量数据库检索)

论文标题: ${title}
论文摘要: ${abstract}
附加文本内容: ${fullText.substring(0, 15000)}`;

        console.log("[Adjudicator] Calling Gemini to analyze: " + title + "...");
        const result = await generateWithRetry(prompt);
        const textResponse = result.response.text();

        const data = JSON.parse(textResponse) as {
            graph: AdjudicatorGraph;
            mismatch: AdjudicatorMismatch;
            solutions: AdjudicatorSolutionInput[];
        };

        console.log("[Adjudicator] Found mismatch: " + data.mismatch.mismatch_type + " (" + data.mismatch.severity + ")");

        // Phase 3: Fetch Pinecone references for each solution
        console.log("[Adjudicator] Querying Pinecone for " + data.solutions.length + " solutions...");
        const finalSolutions = [];

        for (const sol of data.solutions) {
            let references: PineconeReference[] = [];
            try {
                const matches = await findSolutionsForLimitation(sol.pinecone_query, 2);
                references = matches.map((m: any) => ({
                    title: m.metadata?.title || 'Unknown Citation',
                    snippet: m.metadata?.snippet ? (m.metadata.snippet.substring(0, 200) + '...') : '',
                    arxiv_id: m.metadata?.arxiv_id || '',
                    url: m.metadata?.arxiv_id ? "https://arxiv.org/abs/" + m.metadata.arxiv_id : undefined
                }));

                // Generate bilingual recommendation reasons for each found reference
                for (const ref of references) {
                    if (ref.arxiv_id && ref.arxiv_id !== 'unknown' && ref.arxiv_id !== 'error') {
                        try {
                            // Chinese recommendation reason
                            const recPromptZh = `原论文缺陷：${data.mismatch.reasoning}\n检索到对策文献：《${ref.title}》，片段：${ref.snippet}。\n请直接用中文写一句（30字以内）犀利的推荐理由，解释该文献为何能弥补原论文的缺陷。不要输出JSON，直接输出一句话即可。`;
                            const plainTextModel = genAI.getGenerativeModel({ model: "gemini-3.1-pro-preview" });
                            const recResultZh = await plainTextModel.generateContent(recPromptZh);
                            ref.recommendation_reason = recResultZh.response.text().trim();

                            // English recommendation reason
                            const recPromptEn = `Original paper flaw: ${data.mismatch.reasoning_en}\nRetrieved paper: "${ref.title}", snippet: ${ref.snippet}.\nIn one concise English sentence (max 30 words), explain why this paper helps address the flaw of the original paper. Output only one sentence, no JSON.`;
                            const recResultEn = await plainTextModel.generateContent(recPromptEn);
                            ref.recommendation_reason_en = recResultEn.response.text().trim();
                        } catch (e) {
                            console.warn("[Adjudicator] Failed to generate recommendation reason", e);
                        }
                    }
                }

            } catch (err) {
                console.warn("[Adjudicator] Pinecone search failed for query: " + sol.pinecone_query + ". Error: " + err);
                references = [];
            }

            finalSolutions.push({
                direction: sol.direction,
                direction_en: sol.direction_en,
                proposed_method: sol.proposed_method,
                proposed_method_en: sol.proposed_method_en,
                pinecone_query: sol.pinecone_query,
                references
            });
        }

        return {
            graph: data.graph,
            mismatch: data.mismatch,
            solutions: finalSolutions
        };

    } catch (err) {
        console.error("[Adjudicator] Error generating analysis:", err);
        return null;
    }
}
