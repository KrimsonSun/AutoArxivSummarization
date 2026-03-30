
import { getPineconeIndex } from '../model/pinecone';

async function check() {
    try {
        const index = await getPineconeIndex();
        const stats = await index.describeIndexStats();
        console.log('===========================================');
        console.log('📊 PINECONE INDEX STATISTICS');
        console.log('===========================================');
        console.log(`Total Vectors: ${stats.totalRecordCount}`);
        
        // Detailed stats per namespace/dimension
        if (stats.namespaces) {
            Object.entries(stats.namespaces).forEach(([name, data]) => {
                console.log(`Namespace [${name || 'default'}]: ${data.recordCount} vectors`);
            });
        }
        console.log('===========================================');
        
        // Approximate paper count (assuming avg 35 chunks per paper)
        const avgChunks = 35;
        const approxPapers = Math.floor((stats.totalRecordCount || 0) / avgChunks);
        console.log(`💡 Estimated Papers Indexed: ~${approxPapers}`);
    } catch (err: any) {
        console.error('Failed to fetch stats:', err.message);
    }
}

check();
