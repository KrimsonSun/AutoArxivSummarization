import { GoogleGenerativeAI, SchemaType } from "@google/generative-ai";
import { GoogleAIFileManager } from "@google/generative-ai/server";
import { FineGrainedPaperMetadata } from "./types";
import axios from 'axios';
import fs from 'fs';
import path from 'path';
import os from 'os';

export async function extractFineGrainedMetadata(
    pdfUrl: string,
    title: string,
    arxivId: string,
    publishedDate: string
): Promise<FineGrainedPaperMetadata | null> {
    if (!process.env.GEMINI_API_KEY) {
        console.error("GEMINI_API_KEY missing");
        return null;
    }

    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
    const fileManager = new GoogleAIFileManager(process.env.GEMINI_API_KEY);
    
    const tempFilePath = path.join(os.tmpdir(), `${arxivId}.pdf`);

    try {
        // 1. Download PDF locally
        console.log(`  -> Downloading PDF for ${arxivId}...`);
        const pdfResponse = await axios({
            method: 'get',
            url: pdfUrl,
            responseType: 'stream'
        });

        const writer = fs.createWriteStream(tempFilePath);
        pdfResponse.data.pipe(writer);

        await new Promise<void>((resolve, reject) => {
            writer.on('finish', () => resolve());
            writer.on('error', reject);
        });

        // 2. Upload to Gemini File API
        console.log(`  -> Uploading PDF to Gemini...`);
        const uploadResponse = await fileManager.uploadFile(tempFilePath, {
            mimeType: "application/pdf",
            displayName: `${arxivId}.pdf`,
        });
        
        const uploadedFile = uploadResponse.file;

        // 3. Define strict schema to enforce JSON output matching our FineGrainedPaperMetadata
        const schema: any = {
            type: SchemaType.OBJECT,
            properties: {
                target_problem: { type: SchemaType.STRING, description: "Detailed description of the core bottleneck, gap, or problem the paper attempts to address." },
                proposed_solution: { type: SchemaType.STRING, description: "Detailed summary of the proposed method, algorithm, or architecture designed to solve the problem." },
                limitations: {
                    type: SchemaType.ARRAY,
                    items: { type: SchemaType.STRING },
                    description: "List of explicit limitations, drawbacks, assumptions made, or future work mentioned in the paper text."
                },
                datasets_used: {
                    type: SchemaType.ARRAY,
                    items: { type: SchemaType.STRING },
                    description: "Names of any datasets utilized for training, evaluation, or benchmarking."
                },
                domain: {
                    type: SchemaType.ARRAY,
                    items: { type: SchemaType.STRING },
                    description: "Relevant computer science domains (e.g., cs.LG, cs.AI, cs.CV, cs.CL, cs.RO)."
                },
                is_code_available: { type: SchemaType.BOOLEAN, description: "True if a GitHub link or other code repository is mentioned." }
            },
            required: ["target_problem", "proposed_solution", "limitations", "datasets_used", "domain", "is_code_available"]
        };

        const model = genAI.getGenerativeModel({
            model: "gemini-1.5-flash",
            generationConfig: {
                responseMimeType: "application/json",
                responseSchema: schema,
            }
        });

        const prompt = `
        You are a meticulous AI research assistant. Read the attached paper PDF and extract key structured information.
        Be extremely precise with "limitations" and "target_problem".
        
        Paper Title: ${title}

        Extract the structured metadata as JSON.
        `;

        // 4. Generate Content with File URI
        console.log(`  -> Analyzing PDF content with Gemini...`);
        const result = await model.generateContent([
            {
                fileData: {
                    mimeType: uploadedFile.mimeType,
                    fileUri: uploadedFile.uri
                }
            },
            { text: prompt },
        ]);

        // 5. Cleanup Remote File
        await fileManager.deleteFile(uploadedFile.name);

        const jsonText = result.response.text();
        const data = JSON.parse(jsonText);

        return {
            arxiv_id: arxivId,
            title: title,
            published_date: publishedDate,
            ...data
        };
    } catch (err) {
        console.error("Metadata LLM extraction error:", err);
        return null;
    } finally {
        // Cleanup Local File
        if (fs.existsSync(tempFilePath)) {
            fs.unlinkSync(tempFilePath);
        }
    }
}
