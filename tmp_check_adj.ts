import { dbOps } from './src/lib/db';

async function main() {
  const p = await dbOps.getLatestHighlightPaper();
  if (!p) { console.log('No highlight paper found'); process.exit(0); }
  console.log('Paper:', p.title);
  const adj = p.adjudicator_data ? JSON.parse(p.adjudicator_data) : null;
  if (!adj) { console.log('No adjudicator data'); process.exit(0); }
  console.log('Has error?', adj.error || 'none');
  console.log('Solutions count:', adj.solutions?.length ?? 'N/A');
  if (adj.solutions?.[0]) {
    console.log('Solution 0 refs:', JSON.stringify(adj.solutions[0].references, null, 2));
  }
  process.exit(0);
}
main().catch(e => { console.error(e); process.exit(1); });
