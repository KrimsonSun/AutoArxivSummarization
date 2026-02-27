'use client';

import { useLang } from '@/context/LangContext';
import PaperDisplay from '@/components/PaperDisplay';
import SubscriptionForm from '@/components/SubscriptionForm';
import { Languages } from 'lucide-react';

interface Paper {
    title: string;
    authors: string;
    published_date: string;
    summary_zh: string;
    summary_en: string;
    url: string;
}

interface PageContentProps {
    paper: Paper | null;
}

export default function PageContent({ paper }: PageContentProps) {
    const { lang, setLang, t } = useLang();

    return (
        <main className="container">
            <header style={{ textAlign: 'center', marginBottom: '4rem' }} className="animate-fade-in">
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem' }}>
                    <button
                        onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')}
                        className="btn-glass"
                        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', padding: '0.5rem 1rem' }}
                    >
                        <Languages size={16} />
                        {t.toggleLang}
                    </button>
                </div>
                <h1 style={{ fontSize: '3.5rem', marginBottom: '1rem' }}>
                    Auto <span className="text-gradient">ArXiv</span>
                </h1>
                <p className="text-muted" style={{ fontSize: '1.25rem' }}>
                    {t.tagline}
                </p>
            </header>

            {paper ? (
                <PaperDisplay paper={paper} />
            ) : (
                <div className="glass-card animate-fade-in" style={{ textAlign: 'center', padding: '4rem' }}>
                    <p className="text-muted">{t.noPaper}</p>
                </div>
            )}

            <SubscriptionForm />

            <footer style={{ marginTop: '6rem', textAlign: 'center', paddingBottom: '2rem' }} className="text-muted">
                <p>{t.footer}</p>
            </footer>
        </main>
    );
}
