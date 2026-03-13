import * as cheerio from 'cheerio';
const TurndownService = require('turndown');

/**
 * Attempts to fetch the HTML version of an arXiv paper and convert it to Markdown.
 * Tries `ar5iv.labs.arxiv.org` first, then the experimental `arxiv.org/html/`.
 */
export async function extractHtml(arxivId: string): Promise<string | null> {
    const urlsToTry = [
        `https://ar5iv.labs.arxiv.org/html/${arxivId}`,
        `https://arxiv.org/html/${arxivId}`
    ];

    for (const url of urlsToTry) {
        try {
            console.log(`[HTML Extractor] Fetching HTML from ${url}...`);
            const response = await fetch(url);
            if (!response.ok) {
                console.log(`[HTML Extractor] Failed to fetch ${url} (status: ${response.status})`);
                continue;
            }

            const htmlContent = await response.text();
            
            // Basic check to see if we got an actual paper and not an error page
            if (htmlContent.includes("mathjax") || htmlContent.includes("<article>") || htmlContent.includes("ltx_document")) {
                const $ = cheerio.load(htmlContent);
                
                // Remove some noisy elements if present
                $('.ltx_page_footer, .ltx_page_header, nav, footer, script, style').remove();
                
                // Get the main content - structure varies so we try a few target elements
                let mainContent = $('article').html() || $('.ltx_document').html() || $('body').html();
                
                if (mainContent) {
                    const turndownService = new TurndownService({
                        headingStyle: 'atx',
                        codeBlockStyle: 'fenced'
                    });
                    const markdown = turndownService.turndown(mainContent);
                    console.log(`[HTML Extractor] Successfully converted HTML from ${url} to Markdown. Length: ${markdown.length}`);
                    return markdown;
                }
            } else {
                console.log(`[HTML Extractor] Response from ${url} does not appear to be valid paper HTML.`);
            }
        } catch (error) {
            console.error(`[HTML Extractor] Error fetching HTML from ${url}:`, error);
        }
    }

    return null;
}
