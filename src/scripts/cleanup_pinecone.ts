
import { Pinecone } from '@pinecone-database/pinecone';
import dotenv from 'dotenv';
dotenv.config();

async function cleanup() {
    const pc = new Pinecone({ apiKey: process.env.PINECONE_API_KEY! });
    const index = pc.index(process.env.PINECONE_INDEX!);

    console.log(`WARNING: This will delete ALL vectors in index: ${process.env.PINECONE_INDEX}`);
    console.log("Starting deletion in 3 seconds...");
    await new Promise(r => setTimeout(r, 3000));

    await index.deleteAll();
    console.log("Successfully cleared Pinecone index.");
}

cleanup().catch(console.error);
