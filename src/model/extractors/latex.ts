import { spawn } from 'child_process';
import { mkdtemp, rm } from 'fs/promises';
import { tmpdir } from 'os';
import { join } from 'path';
import * as fs from 'fs';
import { pipeline } from 'stream/promises';

/**
 * Attempts to fetch the LaTeX source (tar.gz), extract it, and convert .tex to Markdown using pandoc.
 */
export async function extractLatex(arxivId: string): Promise<string | null> {
    const url = `https://arxiv.org/e-print/${arxivId}`;
    let tempDir: string | undefined;

    try {
        console.log(`[LaTeX Extractor] Fetching e-print source from ${url}...`);
        const response = await fetch(url, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Node.js)'
            }
        });

        if (!response.ok) {
            console.log(`[LaTeX Extractor] Failed to fetch source (status: ${response.status})`);
            return null;
        }

        // Create temporary directory
        tempDir = await mkdtemp(join(tmpdir(), `arxiv-${arxivId}-`));
        const archivePath = join(tempDir, 'source.tar.gz');
        
        // Save the tar.gz
        if (!response.body) throw new Error("No response body");
        // @ts-ignore
        await pipeline(response.body, fs.createWriteStream(archivePath));

        console.log(`[LaTeX Extractor] Source downloaded to ${archivePath}. Extracting...`);

        // Extract tar.gz
        await runCommand('tar', ['-xzf', 'source.tar.gz'], tempDir);

        // Find the main .tex file
        const files = fs.readdirSync(tempDir);
        let mainTexFile = files.find(f => f.endsWith('.tex'));
        
        // If there are multiple .tex files, usually ms.tex or main.tex is the root
        const texFiles = files.filter(f => f.endsWith('.tex'));
        if (texFiles.length > 1) {
            mainTexFile = texFiles.find(f => f.toLowerCase() === 'main.tex') || 
                          texFiles.find(f => f.toLowerCase() === 'ms.tex') || 
                          texFiles[0];
        }

        if (!mainTexFile) {
            console.log(`[LaTeX Extractor] No .tex file found in archive.`);
            return null;
        }

        console.log(`[LaTeX Extractor] Found main .tex file: ${mainTexFile}. Converting with pandoc...`);

        // Convert .tex to Markdown using pandoc
        const markdown = await runCommand('pandoc', [mainTexFile, '-f', 'latex', '-t', 'markdown', '--wrap=none'], tempDir);

        console.log(`[LaTeX Extractor] Successfully converted LaTeX to Markdown. Length: ${markdown.length}`);
        return markdown;

    } catch (error) {
        console.error(`[LaTeX Extractor] Error processing LaTeX for ${arxivId}:`, error);
        return null;
    } finally {
        // Cleanup temp directory
        if (tempDir) {
            try {
                await rm(tempDir, { recursive: true, force: true });
            } catch (cleanupError) {
                console.error(`[LaTeX Extractor] Failed to clean up temp directory ${tempDir}:`, cleanupError);
            }
        }
    }
}

function runCommand(command: string, args: string[], cwd: string): Promise<string> {
    return new Promise((resolve, reject) => {
        const proc = spawn(command, args, { cwd });
        let stdout = '';
        let stderr = '';

        proc.stdout.on('data', (data) => {
            stdout += data.toString();
        });

        proc.stderr.on('data', (data) => {
            stderr += data.toString();
        });

        proc.on('close', (code) => {
            if (code === 0) {
                resolve(stdout);
            } else {
                reject(new Error(`Command ${command} failed with code ${code}: ${stderr}`));
            }
        });

        proc.on('error', (err) => {
            reject(err);
        });
    });
}
