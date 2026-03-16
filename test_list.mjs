import * as dotenv from "dotenv";
dotenv.config();

async function run() {
  try {
    const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${process.env.GEMINI_API_KEY}`);
    const data = await response.json();
    if (data.models) {
        console.log("AVAILABLE MODELS:");
        for (const m of data.models) {
            console.log(`- ${m.name}`);
        }
    } else {
        console.log("Error fetching models:", data);
    }
  } catch(e) {
      console.error(e);
  }
}

run();
