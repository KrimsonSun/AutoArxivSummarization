import { dbOps } from '@/lib/db';
import SubscriptionForm from '@/components/SubscriptionForm';
import PaperDisplay from '@/components/PaperDisplay';
import PageWrapper from '@/components/PageWrapper';
import PageContent from '@/components/PageContent';

export const dynamic = 'force-dynamic';

export default async function Home() {
  const paper = await dbOps.getLatestHighlightPaper() || await dbOps.getLatestPaper();
  return (
    <PageWrapper>
      <PageContent paper={paper} />
    </PageWrapper>
  );
}
