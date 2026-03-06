import { GoogleGenerativeAI } from "@google/generative-ai";

/**
 * The Extractor (Agent A)
 * Responsible for parsing the paper text (or abstract) and extracting pure, objective
 * methodology, architecture, and stated assumptions.
 */
export async function agentA_ExtractMethodology(paperTitle: string, paperText: string) {
    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
    const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash" });

    const prompt = `
    You are Agent A (The Extractor), a meticulous data parser.
    Read the following academic paper text and objectively extract the core Methodology and underlying Assumptions.
    Do not critique. Just state facts.

    Paper Title: ${paperTitle}

    TEXT:
    ${paperText}

    Extract exactly via JSON format:
    {
       "methodology": "Detailed description of the proposed algorithm or architecture.",
       "assumptions": ["List of explicit or implicit assumptions made by the authors."]
    }
  `;

    const result = await model.generateContent({
        contents: [{ role: "user", parts: [{ text: prompt }] }],
        generationConfig: { responseMimeType: "application/json" }
    });

    return JSON.parse(result.response.text());
}

/**
 * The Critic (Agent B)
 * Acts as Reviewer 2. Its job is to find attack vectors, unmentioned edge cases, 
 * and hidden limitations based on Agent A's extraction and the original text.
 */
export async function agentB_Critique(paperTitle: string, paperText: string, extractedData: any) {
    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
    // Using a potentially stronger/more critical model prompt setup
    const model = genAI.getGenerativeModel({
        model: "gemini-2.5-pro", // Pro might be better at finding hidden flaws than Flash
        systemInstruction: "You are a harsh, meticulous, and expert academic reviewer (Reviewer 2)."
    });

    const prompt = `
    You are Agent B (The Critic). Your job is to find weaknesses, hidden flaws, 
    and unmentioned edge cases in the following paper.
    
    Paper Title: ${paperTitle}
    Stated Methodology & Assumptions:
    ${JSON.stringify(extractedData, null, 2)}

    Original Text Snippet for Context:
    ${paperText.substring(0, 3000)} ...

    Provide a highly critical JSON output detailing exactly where this approach fails:
    {
       "vulnerabilities": ["Specific edge cases or metrics they avoided discussing"],
       "fundamental_flaw": "The core limitation that prevents this from solving the broader problem",
       "search_query": "A highly targeted short search phrase (3-5 words) to find literature that specifically solves the 'fundamental_flaw'."
    }
  `;

    const result = await model.generateContent({
        contents: [{ role: "user", parts: [{ text: prompt }] }],
        generationConfig: { responseMimeType: "application/json" }
    });

    return JSON.parse(result.response.text());
}
