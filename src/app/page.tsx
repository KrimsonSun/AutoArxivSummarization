import { dbOps } from '@/lib/db';
import SubscriptionForm from '@/components/SubscriptionForm';
import PaperDisplay from '@/components/PaperDisplay';

export const revalidate = 3600; // 每小时重新验证一次

export default async function Home() {
  const paper = dbOps.getLatestPaper();

  return (
    <main className="container">
      <header style={{ textAlign: 'center', marginBottom: '4rem' }} className="animate-fade-in">
        <h1 style={{ fontSize: '3.5rem', marginBottom: '1rem' }}>
          Auto <span className="text-gradient">ArXiv</span>
        </h1>
        <p className="text-muted" style={{ fontSize: '1.25rem' }}>
          每日从 CS 论文海中捞一根针，AI 为您深度解析。
        </p>
      </header>

      {paper ? (
        <PaperDisplay paper={paper} />
      ) : (
        <div className="glass-card animate-fade-in" style={{ textAlign: 'center', padding: '4rem' }}>
          <p className="text-muted">今天还没有爬取论文，请稍后再来或者直接访问 /api/job?force=true 触发手动抓取。</p>
        </div>
      )}

      <SubscriptionForm />

      <footer style={{ marginTop: '6rem', textAlign: 'center', paddingBottom: '2rem' }} className="text-muted">
        <p>© {new Date().getFullYear()} Auto ArXiv. Built with Next.js & Gemini 2.5 Flash.</p>
      </footer>
    </main>
  );
}
