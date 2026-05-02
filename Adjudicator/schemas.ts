export type AdjudicatorGraphNode = {
    span: string; 
    description: string;      // Chinese
    description_en: string;   // English
}

export type AdjudicatorGraph = {
    premises: AdjudicatorGraphNode[];
    processes: AdjudicatorGraphNode[];
    conclusions: AdjudicatorGraphNode[];
}

export type MismatchType = 
    | 'Dimensional Mismatch' 
    | 'Domain Mismatch' 
    | 'Resource Mismatch' 
    | 'Metric Mismatch' 
    | 'Causality Leap'
    | 'Assumption Constraint';

export type AdjudicatorMismatch = {
    mismatch_type: MismatchType;
    severity: 'Critical' | 'Major';
    broken_edge: string;          // e.g. "Processes -> Conclusions"
    reasoning: string;            // Chinese detailed explanation
    reasoning_en: string;         // English detailed explanation
    testable_question: string; 
}

export type AdjudicatorSolutionInput = {
    direction: string;            // Chinese direction label
    direction_en: string;         // English direction label
    proposed_method: string;      // Chinese method description
    proposed_method_en: string;   // English method description
    pinecone_query: string;       // English search query
}

export type PineconeReference = {
    title: string;
    snippet: string;
    arxiv_id: string;
    url?: string;
    recommendation_reason?: string;     // Chinese
    recommendation_reason_en?: string;  // English
}

export type AdjudicatorFinalResult = {
    graph: AdjudicatorGraph;
    mismatch: AdjudicatorMismatch;
    solutions: {
        direction: string;
        direction_en: string;
        proposed_method: string;
        proposed_method_en: string;
        pinecone_query: string;
        references: PineconeReference[];
    }[];
}
