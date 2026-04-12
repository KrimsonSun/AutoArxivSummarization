export type AdjudicatorGraphNode = {
    span: string; 
    description: string;
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
    broken_edge: string; 
    reasoning: string;
    testable_question: string; 
}

export type AdjudicatorSolutionInput = {
    direction: string;
    proposed_method: string;
    pinecone_query: string;
}

export type PineconeReference = {
    title: string;
    snippet: string;
    arxiv_id: string;
    url?: string;
    recommendation_reason?: string;
}

export type AdjudicatorFinalResult = {
    graph: AdjudicatorGraph;
    mismatch: AdjudicatorMismatch;
    solutions: {
        direction: string;
        proposed_method: string;
        pinecone_query: string;
        references: PineconeReference[];
    }[];
}
