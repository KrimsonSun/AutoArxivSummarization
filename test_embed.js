import { GoogleGenerativeAI } from "@google/generative-ai";
import * as dotenv from "dotenv";

dotenv.config();
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

async function testModel(modelName) {
  try {
    const model = genAI.getGenerativeModel({ model: modelName });
    await model.embedContent("Hello");
    console.log(`[SUCCESS] ${modelName} works for embedContent.`);
  } catch (err) {
    if (err.message.includes("404")) {
      console.log(`[404 NOT FOUND] ${modelName} does not exist or API key lacks access.`);
    } else if (err.message.includes("429")) {
      console.log(`[429 QUOTA EXCEEDED] ${modelName} quota is exhausted.`);
    } else {
      console.log(`[ERROR] ${modelName}:`, err.message);
    }
  }
}

async function run() {
  console.log("Testing embedding models...");
  await testModel("text-embedding-004");
  await testModel("embedding-001");
  await testModel("models/text-embedding-004");
}

run();
