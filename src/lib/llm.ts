import { GoogleGenerativeAI } from '@google/generative-ai';

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY || '');

export interface BilingualSummary {
    zh: string;
    en: string;
}

export async function summarizePaper(title: string, abstract: string): Promise<BilingualSummary | null> {
    const model = genAI.getGenerativeModel({
        model: 'gemini-2.5-flash',
        generationConfig: {
            responseMimeType: "application/json",
        }
    });

    const prompt = `
    You are an expert academic researcher. Your task is to provide a concise, engaging, and clear summary of a Computer Science research paper based on its title and abstract.
    
    You MUST provide the summary in BOTH Chinese (Simplified) and English.
    
    The Chinese summary should be written in a "Tech Blog" style - informative yet accessible.
    The English summary should be professional and academic-friendly.
    
    Return the result EXACTLY in the following JSON format:
    {
      "zh": "Chinese summary here...",
      "en": "English summary here..."
    }

    Paper Title: ${title}
    Abstract: ${abstract}
  `;

    try {
        const result = await model.generateContent(prompt);
        const response = await result.response;
        const text = response.text();

        try {
            return JSON.parse(text) as BilingualSummary;
        } catch (parseError) {
            console.error('Failed to parse Gemini JSON output:', text);
            return null;
        }
    } catch (error: any) {
        console.error('Error calling Gemini API:', error);
        if (error.message) {
            console.error('Error details:', error.message);
        }
        return null;
    }
}
