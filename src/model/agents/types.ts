export interface ExtractedMethodology {
    methodology_summary: string;
    key_claims: {
        span: string;       // Exact quote or close paraphrase from the text
        description: string; // What this claim states
    }[];
    assumptions: {
        span: string;       // Where in text this assumption is made or implied
        description: string; // The explicit or implicit assumption
    }[];
}

export type AttackType =
    | "Boundary generalization"
    | "Assumption mismatch"
    | "Ablation missing"
    | "Dataset shift"
    | "Baselines missing"
    | "Metric gaming"
    | "Causality vs correlation"
    | "Reproducibility";

export type SeverityLevel = "Critical" | "Major" | "Minor";

export interface AttackSchema {
    claim_span: string;          // Must match a span extracted by Agent A
    attack_type: AttackType;
    missing_variable: string;    // e.g., frequency, dataset scale, specific threshold
    testable_question: string;   // A single, clear question for Agent C to search
    evidence_needed: string;     // What specific evidence (theorem, dataset test) is required to patch this hole
    severity: SeverityLevel;
    reasoning: string;           // Brief explanation of why this attack is valid
}

export interface CriticReport {
    attacks: AttackSchema[];
}

export interface BridgeEvidence {
    paper_id: string;
    title: string;
    url: string;
    year: number;
    authors: string[];
    evidence_chunk: string;      // The specific text snippet answering the testable_question
    evidence_type: string;       // e.g., "experiment", "theorem", "ablation"
    satisfies_attack: boolean;   // Does this completely resolve the attack?
}

export interface BridgePlan {
    target_attack_question: string;
    found_solutions: BridgeEvidence[];
}
