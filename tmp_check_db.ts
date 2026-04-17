import { dbOps } from './src/lib/db';
import postgres from 'postgres';

async function main() {
  const sql = postgres(process.env.DATABASE_URL!);
  // Latest 5 papers in DB, showing adj status
  const rows = await sql`
    SELECT arxiv_id, title, created_at,
           adjudicator_data IS NOT NULL as has_adj,
           LEFT(summary_zh, 60) as summary_preview
    FROM papers
    ORDER BY created_at DESC
    LIMIT 5
  `;
  console.log('\n=== Latest 5 papers in DB ===');
  for (const r of rows) {
    console.log(`[${r.created_at.toISOString().slice(0,16)}] ${r.has_adj ? '✅ADJ' : '❌NOADJ'} ${r.title}`);
    console.log(`   Summary preview: ${r.summary_preview}`);
  }
  await sql.end();
  process.exit(0);
}
main().catch(e => { console.error(e); process.exit(1); });
