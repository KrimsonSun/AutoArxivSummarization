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
                            description: { type: SchemaType.STRING }
                        },
                        required: ["span", "description"]
                    }
                },
                processes: {
                    type: SchemaType.ARRAY,
                    items: {
                        type: SchemaType.OBJECT,
                        properties: {
                            span: { type: SchemaType.STRING },
                            description: { type: SchemaType.STRING }
                        },
                        required: ["span", "description"]
                    }
                },
                conclusions: {
                    type: SchemaType.ARRAY,
                    items: {
                        type: SchemaType.OBJECT,
                        properties: {
                            span: { type: SchemaType.STRING },
                            description: { type: SchemaType.STRING }
                        },
                        required: ["span", "description"]
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
                reasoning: { type: SchemaType.STRING, description: 'Detailed explanation of why this is a logical flaw in Chinese.' },
                testable_question: { type: SchemaType.STRING, description: 'A question to challenge the mismatch' }
            },
            required: ["mismatch_type", "severity", "broken_edge", "reasoning", "testable_question"]
        },
        solutions: {
            type: SchemaType.ARRAY,
            items: {
                type: SchemaType.OBJECT,
                properties: {
                    direction: { type: SchemaType.STRING, description: 'e.g., "Theoretical Patch" / "Engineering Solution"' },
                    proposed_method: { type: SchemaType.STRING, description: 'Detail the solution in Chinese.' },
                    pinecone_query: { type: SchemaType.STRING, description: 'A robust search string to search an academic vector database for matching papers.' }
                },
                required: ["direction", "proposed_method", "pinecone_query"]
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

        const prompt = "你是一个极为严谨的计算机科学(机器学习)领域的学术推演官(Adjudicator)。你需要对以下这篇论文进行深度解构和文献匹配。\n\n请将你的分析结果(特别是推理和解决方案部分)**输出为中文**。\n\n目标：\n1. **图结构化提取 (Graph)**：强制将论文解构为3个节点：物理前提/假设 (Premises)、工程/算法过程 (Processes)、最终宣称的结论/效果 (Conclusions)。\n2. **找出逻辑断裂 (Mismatch)**：在这条 \"前提->过程->结论\" 逻辑链条中找出一处最严重、最虚浮的逻辑断裂点，如：分布域偏移、算力不匹配、代理指标与通识能力混淆等（此项仅作审计之用）。\n3. **针对局限性的破局方案 (Solutions)**：仔细阅读并提取论文本身承认的、或你能极度合理推断出的核心技术局限性（Limitation）。针对这个“局限性（Limitation）”，而不是刚才审计出的断裂边，给出3个不同技术方向的跟进、改进或平替方案，并为每个方案写出一个极其适合放入学术向量数据库(Pinecone)寻找相关后续文献的强语义搜索词汇(`pinecone_query`，此查询词请强制使用全英文，堆叠相关的学术关键字！)。\n\n论文标题: " + title + "\n论文摘要: " + abstract + "\n附加文本内容: " + fullText.substring(0, 15000);

        console.log("[Adjudicator] Calling Gemini to analyze: " + title + "...");
        const result = await model.generateContent(prompt);
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

        // In parallel or sequentially
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

                // Generate specific Chinese recommendation reason for each found reference
                for (const ref of references) {
                    if (ref.arxiv_id && ref.arxiv_id !== 'unknown' && ref.arxiv_id !== 'error') {
                        try {
                            const recPrompt = `原论文缺陷：${data.mismatch.reasoning}\n检索到对策文献：《${ref.title}》，片段：${ref.snippet}。\n请直接用中文写一句（30字以内）犀利的推荐理由，解释该文献为何能弥补原论文的缺陷。不要输出JSON，直接输出一句话即可。`;
                            const plainTextModel = genAI.getGenerativeModel({ model: "gemini-3.1-pro-preview" });
                            const recResult = await plainTextModel.generateContent(recPrompt);
                            ref.recommendation_reason = recResult.response.text().trim();
                        } catch (e) {
                            console.warn("[Adjudicator] Failed to generate recommendation reason", e);
                        }
                    }
                }

                // If search returns 0 real matches, leave references empty — no fake entries
                // The frontend handles empty references gracefully

            } catch (err) {
                console.warn("[Adjudicator] Pinecone search failed for query: " + sol.pinecone_query + ". Error: " + err);
                // Leave references empty — do NOT write fake error entries into DB
                references = [];
            }

            finalSolutions.push({
                direction: sol.direction,
                proposed_method: sol.proposed_method,
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
        return null; // Fail gracefully so it doesn't crash the pipeline, but we just won't have adjudicator_data
    }
}
