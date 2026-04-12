import { dbOps } from './src/lib/db';

async function check() {
  const paper = await dbOps.getLatestPaper();
  console.log("Latest Paper ID:", paper?.arxiv_id);
  console.log("Title:", paper?.title);
  console.log("Has adjudicator_data:", !!paper?.adjudicator_data);
  if (paper?.adjudicator_data) {
     console.log("Adjudicator JSON Snippet:", paper.adjudicator_data.substring(0, 100));
  }
}

check().catch(console.error).finally(() => process.exit(0));
