import { dbOps } from './src/lib/db';
import { runAdjudicator } from './Adjudicator/index';

async function main() {
  const paper = await dbOps.getLatestPaper();
  if(!paper) {
    console.log("No paper in DB.");
    return;
  }
  console.log("Running Adjudicator on: " + paper.title);
  try {
    const result = await runAdjudicator(paper.title, paper.abstract, "");
    if(result) {
      await dbOps.savePaper({...paper, adjudicator_data: JSON.stringify(result)});
      console.log("Successfully saved adjudicator_data to SQLite.");
    } else {
      console.log("Adjudicator failed to return format.");
    }
  } catch (e) {
    console.error("Adjudicator crashed", e);
  }
}
main().catch(console.error);
