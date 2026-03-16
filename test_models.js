import { GoogleGenerativeAI } from "@google/generative-ai";
import * as dotenv from "dotenv";

dotenv.config();

const apiKey = process.env.GEMINI_API_KEY;
if (!apiKey) {
  console.error("No API key found in .env");
  process.exit(1);
}

const genAI = new GoogleGenerativeAI(apiKey);

async function testModel(modelName) {
  try {
    const model = genAI.getGenerativeModel({ model: modelName });
    await model.generateContent("Hello");
    console.log(`[SUCCESS] ${modelName} works.`);
  } catch (err) {
    if (err.message.includes("404")) {
      console.log(`[404 NOT FOUND] ${modelName} does not exist or API key lacks access.`);
    } else if (err.message.includes("429")) {
      console.log(`[429 QUOTA EXCEEDED] ${modelName} exists, but quota is exhausted.`);
      console.log("  ->", err.message.split('\n')[0]);
    } else {
      console.log(`[ERROR] ${modelName}:`, err.message);
    }
  }
}

async function run() {
  console.log("Testing text generation models...");
  await testModel("gemini-1.5-flash");
  await testModel("gemini-1.5-pro");
  await testModel("gemini-2.0-flash");
  await testModel("gemini-2.0-flash-lite");
  await testModel("gemini-2.0-flash-exp");
  await testModel("text-embedding-004");
  await testModel("gemini-3.0-flash-lite");
}

run();
