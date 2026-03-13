import { extractHtml } from '../model/extractors/html';
import { extractLatex } from '../model/extractors/latex';
import { extractPdfWithDocling } from '../model/extractors/pdf';

async function run() {
    const testArxivId = '2403.05530'; // Replace with a known ID to test

    console.log(`\n=== Testing HTML Extractor for ${testArxivId} ===`);
    const htmlRes = await extractHtml(testArxivId);
    if (htmlRes) {
        console.log(`HTML SUCCESS: First 200 chars: ${htmlRes.substring(0, 200)}...\n`);
    } else {
        console.log(`HTML FAILED.\n`);
    }

    console.log(`\n=== Testing LaTeX Extractor for ${testArxivId} ===`);
    const latexRes = await extractLatex(testArxivId);
    if (latexRes) {
        console.log(`LaTeX SUCCESS: First 200 chars: ${latexRes.substring(0, 200)}...\n`);
    } else {
        console.log(`LaTeX FAILED.\n`);
    }

    console.log(`\n=== Testing PDF/Docling Extractor for ${testArxivId} ===`);
    const doclingRes = await extractPdfWithDocling(testArxivId);
    if (doclingRes) {
        console.log(`PDF/Docling SUCCESS: First 200 chars: ${doclingRes.substring(0, 200)}...\n`);
    } else {
        console.log(`PDF/Docling FAILED.\n`);
    }
}

run().catch(console.error);
