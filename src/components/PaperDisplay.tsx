'use client';

import { useLang } from '@/context/LangContext';
import { ExternalLink, BookOpen, User, Calendar } from 'lucide-react';
import { format } from 'date-fns';
import { zhCN } from 'date-fns/locale';

interface PaperProps {
    paper: {
        title: string;
        authors: string;
        published_date: string;
        summary_zh: string;
        summary_en: string;
        url: string;
    };
}

export default function PaperDisplay({ paper }: PaperProps) {
    const { lang, t } = useLang();

    return (
        <div className="glass-card animate-fade-in" style={{ animationDelay: '0.1s' }}>
            <div style={{ marginBottom: '1.5rem' }}>
                <div className="badge">{t.todaySelection}</div>
            </div>

            <h2 style={{ fontSize: '2rem', marginBottom: '1.5rem', lineHeight: '1.3' }}>
                {paper.title}
            </h2>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1.5rem', marginBottom: '2rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }} className="text-muted">
                    <User size={18} />
                    <span style={{ fontSize: '0.9rem' }}>{paper.authors}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }} className="text-muted">
                    <Calendar size={18} />
                    <span style={{ fontSize: '0.9rem' }}>
                        {lang === 'zh'
                            ? format(new Date(paper.published_date), 'yyyy年MM月dd日', { locale: zhCN })
                            : format(new Date(paper.published_date), 'MMM dd, yyyy')
                        }
                    </span>
                </div>
            </div>

            <div style={{ marginBottom: '2.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                    <BookOpen size={24} className="text-primary" />
                    <h3 style={{ fontSize: '1.25rem' }}>{t.aiSummary}</h3>
                </div>
                <div
                    className="prose"
                    dangerouslySetInnerHTML={{
                        __html: (lang === 'zh' ? paper.summary_zh : paper.summary_en).replace(/\n/g, '<br>')
                    }}
                />
            </div>

            <div style={{ display: 'flex', gap: '1rem' }}>
                <a
                    href={paper.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-primary"
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', textDecoration: 'none' }}
                >
                    <span>{t.readOriginal}</span>
                    <ExternalLink size={18} />
                </a>
            </div>
        </div>
    );
}
