export interface FineGrainedPaperMetadata {
    arxiv_id: string;
    title: string;
    published_date: string;
    domain: string[]; // e.g., ["cs.LG", "cs.AI", "cs.CV", "cs.CL"]
    target_problem: string; // The core challenge or problem the paper addresses
    proposed_solution: string; // How they solve it
    limitations: string[]; // Explicitly mentioned limitations or areas for future work
    datasets_used: string[]; // Names of datasets mentioned
    is_code_available: boolean; // True if the code repository is available (e.g., GitHub)
}

export interface PineconePaperVector {
    id: string; // arxiv_id + unique suffix (e.g., 2401.xxxx_solution)
    values: number[]; // resulting embedding vector
    metadata: Record<string, any>; // Pinecone valid typing for metadata (strings, numbers, booleans, string[])
}
