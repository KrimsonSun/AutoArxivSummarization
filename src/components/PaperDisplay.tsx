'use client';

import { useLang } from '@/context/LangContext';
import {
    ExternalLink, BookOpen, User, Calendar,
    Zap, FlaskConical, Database, BarChart2, Lightbulb,
    AlertTriangle, GitMerge, FileSearch, ArrowRight, Activity
} from 'lucide-react';
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
        adjudicator_data?: string;
    };
}

interface ParsedSection {
    title: string;
    contentHtml: string;
}

interface ParsedSummary {
    tldrHtml: string | null;
    sections: ParsedSection[];
}

/** Convert common markdown to safe HTML */
function markdownToHtml(text: string): string {
    return text
        // **bold** → <strong>
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        // *italic* → <em>
        .replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>')
        // Numbered list items "1.  text" or "1. text"
        .replace(/^(\d+)\.\s{1,3}(.+)$/gm, '<li>$2</li>')
        // Bullet list items "* text" or "- text" (not bold **)
        .replace(/^[*\-]\s+(.+)$/gm, '<li>$1</li>')
        // Wrap consecutive <li> in <ul> (simple approximation)
        .replace(/(<li>[\s\S]*?<\/li>(?:\n<li>[\s\S]*?<\/li>)*)/g, (match) => {
            // If the first char of sub-match is from a numbered item, use ol
            return `<ul style="padding-left:1.25rem;margin:0.5rem 0;display:flex;flex-direction:column;gap:0.25rem;">${match}</ul>`;
        })
        // Remaining newlines → <br>
        .replace(/\n/g, '<br>');
}

/** Parse "TL;DR: ...\n\nSECTION: Title\ncontent\nSECTION: ..." */
function parseSummary(text: string): ParsedSummary {
    // Capture TL;DR: everything up to the first double newline + SECTION or end
    const tldrMatch = text.match(/TL;DR:\s*([\s\S]+?)(?=\n\s*\nSECTION:|\n\s*SECTION:|$)/i);
    const tldrRaw = tldrMatch ? tldrMatch[1].trim() : null;
    const tldrHtml = tldrRaw ? markdownToHtml(tldrRaw) : null;

    // Split on SECTION: (with optional preceding newlines)
    const sectionParts = text.split(/\n+SECTION:\s*/);
    const sections: ParsedSection[] = [];

    for (let i = 1; i < sectionParts.length; i++) {
        const firstNewline = sectionParts[i].indexOf('\n');
        if (firstNewline === -1) continue;
        const title = sectionParts[i].slice(0, firstNewline).trim();
        const rawContent = sectionParts[i].slice(firstNewline + 1).trim();
        if (title && rawContent) {
            sections.push({ title, contentHtml: markdownToHtml(rawContent) });
        }
    }

    return { tldrHtml, sections };
}

function getSectionIcon(title: string) {
    const t = title.toLowerCase();
    if (t.includes('method') || t.includes('方法') || t.includes('approach') || t.includes('架构')) return <FlaskConical size={15} />;
    if (t.includes('data') || t.includes('数据')) return <Database size={15} />;
    if (t.includes('performance') || t.includes('result') || t.includes('效果') || t.includes('表现')) return <BarChart2 size={15} />;
    return <Lightbulb size={15} />;
}

export default function PaperDisplay({ paper }: PaperProps) {
    const { lang, t } = useLang();
    const rawSummary = lang === 'zh' ? paper.summary_zh : paper.summary_en;
    const { tldrHtml, sections } = parseSummary(rawSummary);
    const hasStructure = tldrHtml !== null || sections.length > 0;

    let adjudicatorResult = null;
    if (paper.adjudicator_data) {
        try {
            adjudicatorResult = JSON.parse(paper.adjudicator_data);
        } catch (e) {
            console.error("Failed to parse adjudicator data", e);
        }
    }

    return (
        <div className="glass-card animate-fade-in" style={{ animationDelay: '0.1s' }}>
            {/* Header badge */}
            <div style={{ marginBottom: '1.5rem' }}>
                <div className="badge">{t.todaySelection}</div>
            </div>

            <h2 style={{ fontSize: '1.8rem', marginBottom: '1.5rem', lineHeight: '1.3' }}>
                {paper.title}
            </h2>

            {/* Meta row */}
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
                            : format(new Date(paper.published_date), 'MMM dd, yyyy')}
                    </span>
                </div>
            </div>

            {/* AI Analysis */}
            <div style={{ marginBottom: '2.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
                    <BookOpen size={22} className="text-primary" />
                    <h3 style={{ fontSize: '1.2rem', margin: 0 }}>{t.aiSummary}</h3>
                </div>

                {hasStructure ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

                        {/* ═══ TL;DR callout ═══ */}
                        {tldrHtml && (
                            <div style={{
                                display: 'flex',
                                gap: '0.875rem',
                                alignItems: 'flex-start',
                                background: 'linear-gradient(135deg, rgba(99,102,241,0.18), rgba(168,85,247,0.12))',
                                border: '1.5px solid rgba(99,102,241,0.4)',
                                borderRadius: '14px',
                                padding: '1rem 1.25rem',
                            }}>
                                <Zap size={20} style={{ color: 'var(--primary)', flexShrink: 0, marginTop: '2px' }} />
                                <div>
                                    <p style={{
                                        margin: '0 0 0.25rem',
                                        fontSize: '0.7rem',
                                        fontWeight: 800,
                                        letterSpacing: '0.1em',
                                        textTransform: 'uppercase',
                                        color: 'var(--primary)',
                                    }}>
                                        TL;DR
                                    </p>
                                    <p
                                        style={{ margin: 0, fontWeight: 600, lineHeight: 1.65, fontSize: '0.95rem' }}
                                        dangerouslySetInnerHTML={{ __html: tldrHtml }}
                                    />
                                </div>
                            </div>
                        )}

                        {/* ═══ Sections ═══ */}
                        {sections.map((section, i) => (
                            <div key={i} style={{
                                background: 'rgba(255,255,255,0.03)',
                                border: '1px solid var(--border)',
                                borderRadius: '12px',
                                padding: '1rem 1.25rem',
                            }}>
                                {/* Section title */}
                                <div style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem',
                                    marginBottom: '0.75rem',
                                    paddingBottom: '0.5rem',
                                    borderBottom: '1px solid rgba(99,102,241,0.2)',
                                }}>
                                    <span style={{ color: 'var(--primary)' }}>
                                        {getSectionIcon(section.title)}
                                    </span>
                                    <h4 style={{
                                        margin: 0,
                                        fontSize: '0.8rem',
                                        fontWeight: 800,
                                        textTransform: 'uppercase',
                                        letterSpacing: '0.08em',
                                        color: 'var(--primary)',
                                    }}>
                                        {section.title}
                                    </h4>
                                </div>

                                {/* Section content — markdown rendered */}
                                <div
                                    style={{ lineHeight: 1.75, fontSize: '0.93rem' }}
                                    dangerouslySetInnerHTML={{ __html: section.contentHtml }}
                                />
                            </div>
                        ))}
                    </div>
                ) : (
                    /* Fallback plain text */
                    <div
                        className="prose"
                        dangerouslySetInnerHTML={{ __html: rawSummary.replace(/\n/g, '<br>') }}
                    />
                )}
            </div>

            {/* Adjudicator Analysis Block */}
            {adjudicatorResult && (
                <div style={{ marginBottom: '2.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
                        <Activity size={22} className="text-primary" style={{ color: '#f43f5e' }} />
                        <h3 style={{ fontSize: '1.2rem', margin: 0, color: '#f43f5e' }}>批判性分析与破局 (Adjudicator Analysis)</h3>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                        
                        {/* 1. Mismatch Warning Card */}
                        <div style={{
                            background: 'rgba(244, 63, 94, 0.05)',
                            border: '1px solid rgba(244, 63, 94, 0.3)',
                            borderRadius: '12px',
                            padding: '1.25rem',
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                                <AlertTriangle size={18} color="#f43f5e" />
                                <h4 style={{ margin: 0, color: '#f43f5e', fontSize: '0.95rem' }}>
                                    逻辑错配诊断: {adjudicatorResult.mismatch.mismatch_type} 
                                    <span style={{ marginLeft: '0.5rem', fontSize: '0.75rem', padding: '0.1rem 0.4rem', background: '#f43f5e', color: '#fff', borderRadius: '4px' }}>
                                        {adjudicatorResult.mismatch.severity}
                                    </span>
                                </h4>
                            </div>
                            <div style={{ fontSize: '0.9rem', lineHeight: 1.6, color: 'var(--foreground)' }}>
                                <p style={{ margin: '0 0 0.5rem 0' }}><strong>断裂边：</strong> {adjudicatorResult.mismatch.broken_edge}</p>
                                <p style={{ margin: 0 }}><strong>诊断原因：</strong> {adjudicatorResult.mismatch.reasoning}</p>
                            </div>
                        </div>

                        {/* 2. Structured Graph view */}
                        <div style={{
                            background: 'rgba(255,255,255,0.02)',
                            border: '1px solid var(--border)',
                            borderRadius: '12px',
                            padding: '1.25rem',
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', color: 'var(--primary)' }}>
                                <GitMerge size={16} />
                                <h4 style={{ margin: 0, fontSize: '0.9rem' }}>论文架构解构</h4>
                            </div>
                            
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr auto 1fr', gap: '0.5rem', alignItems: 'center' }}>
                                {/* Premises */}
                                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.75rem', borderRadius: '8px', fontSize: '0.8rem' }}>
                                    <div style={{ fontWeight: 600, color: '#a855f7', marginBottom: '0.25rem' }}>前提 (Premises)</div>
                                    <ul style={{ margin: 0, paddingLeft: '1rem', color: 'var(--muted)' }}>
                                        {adjudicatorResult.graph.premises.map((p: any, i: number) => <li key={i}>{p.description}</li>)}
                                    </ul>
                                </div>
                                <ArrowRight size={16} className="text-muted" />
                                
                                {/* Processes */}
                                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.75rem', borderRadius: '8px', fontSize: '0.8rem' }}>
                                    <div style={{ fontWeight: 600, color: '#3b82f6', marginBottom: '0.25rem' }}>过程 (Processes)</div>
                                    <ul style={{ margin: 0, paddingLeft: '1rem', color: 'var(--muted)' }}>
                                        {adjudicatorResult.graph.processes.map((p: any, i: number) => <li key={i}>{p.description}</li>)}
                                    </ul>
                                </div>
                                <ArrowRight size={16} className="text-muted" />

                                {/* Conclusions */}
                                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.75rem', borderRadius: '8px', fontSize: '0.8rem' }}>
                                    <div style={{ fontWeight: 600, color: '#10b981', marginBottom: '0.25rem' }}>结论 (Conclusions)</div>
                                    <ul style={{ margin: 0, paddingLeft: '1rem', color: 'var(--muted)' }}>
                                        {adjudicatorResult.graph.conclusions.map((p: any, i: number) => <li key={i}>{p.description}</li>)}
                                    </ul>
                                </div>
                            </div>
                        </div>

                        {/* 3. Proposed Solutions + Pinecone Results */}
                        <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', marginTop: '1rem' }}>
                                <FileSearch size={18} className="text-primary" />
                                <h4 style={{ margin: 0, fontSize: '1rem' }}>建设性破局方案 (Solutions)</h4>
                            </div>
                            
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                                {adjudicatorResult.solutions.map((sol: any, idx: number) => (
                                    <div key={idx} style={{
                                        background: 'rgba(255,255,255,0.03)',
                                        borderLeft: '4px solid var(--primary)',
                                        padding: '1rem',
                                        borderRadius: '0 8px 8px 0'
                                    }}>
                                        <div style={{ fontWeight: 600, fontSize: '0.95rem', marginBottom: '0.5rem', color: 'var(--primary)' }}>
                                            方向 {idx + 1}: {sol.direction}
                                        </div>
                                        <div style={{ fontSize: '0.85rem', marginBottom: '1rem', lineHeight: 1.5 }}>
                                            {sol.proposed_method}
                                        </div>
                                        
                                        {sol.references && sol.references.length > 0 && (
                                            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.75rem', borderRadius: '8px' }}>
                                                <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                                    <Database size={12} /> Pinecone 知识库推荐
                                                </div>
                                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                                    {sol.references.map((r: any, rIdx: number) => (
                                                        <div key={rIdx} style={{ fontSize: '0.8rem' }}>
                                                            {r.url ? (
                                                                <a href={r.url} target="_blank" rel="noreferrer" style={{ color: '#60a5fa', textDecoration: 'none', fontWeight: 500 }}>
                                                                    {r.title}
                                                                </a>
                                                            ) : (
                                                                <span style={{ color: '#9ca3af', fontWeight: 500 }}>{r.title}</span>
                                                            )}
                                                            <div style={{ color: 'var(--muted)', marginTop: '0.2rem', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', fontStyle: 'italic' }}>
                                                                " {r.snippet} "
                                                            </div>
                                                            {r.recommendation_reason && (
                                                                <div style={{ marginTop: '0.4rem', color: '#10b981', fontSize: '0.75rem', fontWeight: 600, background: 'rgba(16, 185, 129, 0.1)', padding: '0.4rem 0.6rem', borderRadius: '6px', borderLeft: '3px solid #10b981' }}>
                                                                    💡 推荐理由: {r.recommendation_reason}
                                                                </div>
                                                            )}
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>

                    </div>
                </div>
            )}

            {/* CTA */}
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
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
