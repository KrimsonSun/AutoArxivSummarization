import { agentA_ExtractMethodology, agentB_Critique } from "./agents/critic.ts";
import { agentC_BridgeAndSolve } from "./agents/bridge.ts";

export async function runAdvancedDebatePipeline(paperTitle: string, abstractOrText: string) {
    console.log("\n=======================================================");
    console.log(`[ADVANCED DEBATE] Processing: "${paperTitle}"`);
    console.log("=======================================================\n");

    // --- Step 1: Objective Extraction ---
    console.log("[Phase 1] Agent A (Extractor) parsing text...");
    const extractedData = await agentA_ExtractMethodology(paperTitle, abstractOrText);
    if (!extractedData) return console.error("Failed to extract methodology.");

    console.log(`-> Extracted ${extractedData.key_claims.length} claims and ${extractedData.assumptions.length} assumptions.`);

    // --- Step 2: Structured Counterfactual Attacks ---
    console.log("\n[Phase 2] Agent B (Critic) launching structured attacks...");
    const criticReport = await agentB_Critique(paperTitle, abstractOrText, extractedData);
    if (!criticReport || criticReport.attacks.length === 0) {
        return console.log("-> Agent B found no valid attack vectors.");
    }

    console.log(`-> Generated ${criticReport.attacks.length} strict attack schemas.`);

    // --- Step 3: Evidence Level Bridging ---
    console.log("\n[Phase 3] Agent C (Bridge) expanding citation graph and fetching evidence...");

    const debateOutcomes = [];

    for (const attack of criticReport.attacks) {
        console.log(`\n--- ATTACK TARGET: [${attack.severity}] ${attack.attack_type} ---`);
        console.log(`  Target Span: "${attack.claim_span}"`);
        console.log(`  Reasoning:   ${attack.reasoning}`);
        console.log(`  Queryizing:  "${attack.testable_question}" ...`);

        const bridgePlan = await agentC_BridgeAndSolve(attack);
        debateOutcomes.push({ attack, bridgePlan });
    }

    // --- FINAL REPORT ---
    console.log("\n=======================================================");
    console.log("                FINAL DEBATE VERDICT");
    console.log("=======================================================");

    debateOutcomes.forEach((outcome, idx) => {
        console.log(`\n[Vulnerability #${idx + 1}] ${outcome.attack.attack_type}`);
        console.log(`   Focus: ${outcome.attack.missing_variable}`);
        console.log(`   Needed: ${outcome.attack.evidence_needed}`);

        if (outcome.bridgePlan.found_solutions.length > 0) {
            console.log(`\n   >>> 🟢 AGENT C FOUND EVIDENCE (${outcome.bridgePlan.found_solutions.length} papers) <<<`);
            outcome.bridgePlan.found_solutions.forEach((sol, sIdx) => {
                console.log(`       Evidence ${sIdx + 1}: [${sol.evidence_type.toUpperCase()}] "${sol.evidence_chunk}"`);
                console.log(`       Source: ${sol.title} (${sol.year}) | ${sol.url}`);
            });
        } else {
            console.log(`\n   >>> 🔴 AGENT C FAILED TO FIND SATISFACTORY EVIDENCE (Open Research Gap) <<<`);
        }
    });
    console.log("\n=======================================================\n");
}
