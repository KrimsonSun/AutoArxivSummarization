import { GoogleGenerativeAI } from "@google/generative-ai";
import * as dotenv from "dotenv";

dotenv.config();
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

async function testModel(modelName) {
  try {
    const model = genAI.getGenerativeModel({ model: modelName });
    const res = await model.embedContent("Hello");
    console.log(`[SUCCESS] ${modelName} works. Dims: ${res.embedding.values.length}`);
  } catch (err) {
    if (err.message.includes("404")) {
      console.log(`[404] ${modelName}`);
    } else {
      console.log(`[ERROR] ${modelName}:`, err.message.split('\n')[0]);
    }
  }
}

async function run() {
  await testModel("text-embedding-004");
  await testModel("models/text-embedding-004");
  await testModel("text-embedding-004-preview");
  await testModel("embedding-001");
}

run();
