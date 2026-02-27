const { GoogleGenerativeAI } = require('@google/generative-ai');
require('dotenv').config({ path: '.env.local' });

async function test() {
    const apiKey = process.env.GEMINI_API_KEY;
    console.log('Using API Key:', apiKey ? (apiKey.substring(0, 5) + '...') : 'MISSING');

    if (!apiKey) {
        console.error('Missing GEMINI_API_KEY in .env.local');
        return;
    }

    const genAI = new GoogleGenerativeAI(apiKey);

    const modelsToTest = ['gemini-1.5-flash', 'gemini-1.5-flash-latest', 'gemini-pro', 'gemini-1.0-pro'];

    for (const modelName of modelsToTest) {
        try {
            console.log(`\n--- Testing Model: ${modelName} ---`);
            const model = genAI.getGenerativeModel({ model: modelName });
            const result = await model.generateContent('Hello');
            const response = await result.response;
            console.log(`Success with ${modelName}:`, response.text().substring(0, 50) + '...');
            return; // Exit if one works
        } catch (error) {
            console.error(`Failed with ${modelName}:`, error.message || error);
        }
    }
}

test();
