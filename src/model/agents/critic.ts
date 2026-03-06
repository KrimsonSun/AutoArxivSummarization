import { GoogleGenerativeAI, Schema, SchemaType } from "@google/generative-ai";
import { AttackSchema, CriticReport, ExtractedMethodology } from "./types.ts";

/**
 * Agent A (The Extractor)
 * Extracts objective methodology, claims, and assumptions with text spans.
 */
export async function agentA_ExtractMethodology(paperTitle: string, paperText: string): Promise<ExtractedMethodology | null> {
    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);

    const schema: Schema = {
        type: SchemaType.OBJECT,
        properties: {
            methodology_summary: { type: SchemaType.STRING },
            key_claims: {
                type: SchemaType.ARRAY,
                items: {
                    type: SchemaType.OBJECT,
                    properties: {
                        span: { type: SchemaType.STRING, description: "Exact quote or close paraphrase" },
                        description: { type: SchemaType.STRING }
                    },
                    required: ["span", "description"]
                }
            },
            assumptions: {
                type: SchemaType.ARRAY,
                items: {
                    type: SchemaType.OBJECT,
                    properties: {
                        span: { type: SchemaType.STRING, description: "Exact quote or context where assumption is made" },
                        description: { type: SchemaType.STRING, description: "The explicit or implicit assumption" }
                    },
                    required: ["span", "description"]
                }
            }
        },
        required: ["methodology_summary", "key_claims", "assumptions"]
    };

    const model = genAI.getGenerativeModel({
        model: "gemini-2.5-flash",
        generationConfig: { responseMimeType: "application/json", responseSchema: schema }
    });

    const prompt = `
    You are Agent A (The Extractor), a meticulous data parser.
    Read the academic paper text and objectively extract the core Methodology, Key Claims, and underlying Assumptions.
    For every claim or assumption, provide a "span" (a closely matching text excerpt).
    Do not critique. Just state facts.

    Title: ${paperTitle}
    Text: ${paperText}
  `;

    try {
        const result = await model.generateContent(prompt);
        return JSON.parse(result.response.text()) as ExtractedMethodology;
    } catch (error) {
        console.error("[Agent A] Extraction failed:", error);
        return null;
    }
}

/**
 * Neuro-Symbolic Agent B (The Critic / Reviewer 2)
 * Phase 1 (Neuro): LLM extracts structured flags/entities from claims.
 * Phase 2 (Symbolic): Hard-coded TypeScript rules map flags to Attack Schemas.
 */
export async function agentB_Critique(paperTitle: string, paperText: string, extractedData: ExtractedMethodology): Promise<CriticReport | null> {
    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);

    // Phase 1: Neural Entity & Flag Extraction (No reasoning, just tagging)
    const neuroSchema: Schema = {
        type: SchemaType.OBJECT,
        properties: {
            claim_metrics: {
                type: SchemaType.ARRAY,
                items: {
                    type: SchemaType.OBJECT,
                    properties: {
                        claim_span: { type: SchemaType.STRING },
                        primary_metrics: { type: SchemaType.ARRAY, items: { type: SchemaType.STRING }, description: "e.g. ['BLEU', 'Accuracy']" },
                        has_efficiency_metrics: { type: SchemaType.BOOLEAN, description: "Does it measure latency, memory, or speed?" },
                        dataset_count: { type: SchemaType.NUMBER, description: "Number of datasets used" },
                        compares_to_baselines: { type: SchemaType.BOOLEAN, description: "Does it explicitly compare to prior state-of-the-art?" },
                        has_ablation_study: { type: SchemaType.BOOLEAN, description: "Did they test removing parts of their method?" }
                    },
                    required: ["claim_span", "primary_metrics", "has_efficiency_metrics", "dataset_count", "compares_to_baselines", "has_ablation_study"]
                }
            }
        },
        required: ["claim_metrics"]
    };

    const model = genAI.getGenerativeModel({
        model: "gemini-2.5-flash",
        systemInstruction: "You are a precise data tagger. You only extract facts into the requested schema without judgment.",
        generationConfig: { responseMimeType: "application/json", responseSchema: neuroSchema }
    });

    const prompt = `
    Analyze the following extracted claims and the original text.
    For each claim, determine its evaluation metrics, dataset scale, and experimental setup based ONLY on the text.
    
    Paper Title: ${paperTitle}
    
    EXTRACTED METADATA:
    ${JSON.stringify(extractedData, null, 2)}

    Original Text Context:
    ${paperText.substring(0, 4000)}...
    `;

    let taggedData: any;
    try {
        const result = await model.generateContent(prompt);
        taggedData = JSON.parse(result.response.text());
    } catch (error) {
        console.error("[Agent B Neural Phase] Extraction failed:", error);
        return null;
    }

    // Phase 2: Symbolic Rule Engine (Deterministic Attack Generation)
    const attacks: AttackSchema[] = [];

    for (const claimFlag of taggedData.claim_metrics) {
        // Rule 1: Efficiency Missing
        if (!claimFlag.has_efficiency_metrics) {
            attacks.push({
                claim_span: claimFlag.claim_span,
                attack_type: "Assumption mismatch",
                missing_variable: "Computational Efficiency Metrics (Latency, Memory, FLOPS)",
                testable_question: `Does the method proposed in this paper maintain practical inference latency and memory efficiency, or does it trade computational complexity for its performance gains on ${claimFlag.primary_metrics.join(', ')}?`,
                evidence_needed: "Empirical benchmarks showing memory footprint and real-time inference latency compared to baselines.",
                severity: "Major",
                reasoning: "[Rule T1] Claims of superiority based solely on qualitative/accuracy metrics implicitly assume unbounded or acceptable computational costs, which is rarely true in deployment."
            });
        }

        // Rule 2: Boundary Generalization (Low Dataset Diversity)
        if (claimFlag.dataset_count < 3) {
            attacks.push({
                claim_span: claimFlag.claim_span,
                attack_type: "Boundary generalization",
                missing_variable: "Diverse data distributions (Cross-domain, Out-of-distribution)",
                testable_question: `How does the proposed approach generalize across diverse datasets and noisy, out-of-distribution conditions beyond its limited evaluation setup?`,
                evidence_needed: "Results on at least 3+ diverse datasets, particularly evaluating robustness against domain shift.",
                severity: "Critical",
                reasoning: `[Rule G1] Evaluated on only ${claimFlag.dataset_count} dataset(s). High risk of overfitting to specific data distributions.`
            });
        }

        // Rule 3: Ablation Missing
        if (!claimFlag.has_ablation_study) {
            attacks.push({
                claim_span: claimFlag.claim_span,
                attack_type: "Ablation missing",
                missing_variable: "Component contribution analysis",
                testable_question: `Are all architectural components essential, or can the performance gains be attributed to a specific subset of the proposed methodology?`,
                evidence_needed: "A rigorous ablation study isolating the impact of each novel component.",
                severity: "Major",
                reasoning: "[Rule A1] Complex methodologies require ablations to prove that gains are not merely from increased capacity or hyperparameter tuning."
            });
        }
    }

    // Ensure we don't spam too many attacks, take top 4 unique logical attacks
    const uniqueAttacks = Array.from(new Map(attacks.map(a => [a.attack_type + a.claim_span, a])).values()).slice(0, 4);

    return { attacks: uniqueAttacks };
}
