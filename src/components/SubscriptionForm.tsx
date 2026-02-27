'use client';

import { useState } from 'react';
import { Mail, Loader2, CheckCircle2 } from 'lucide-react';
import { useLang } from '@/context/LangContext';

export default function SubscriptionForm() {
    const { lang, t } = useLang();
    const [email, setEmail] = useState('');
    const [emailLang, setEmailLang] = useState<'zh' | 'en'>(lang);
    const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setStatus('loading');

        try {
            const response = await fetch('/api/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, language: emailLang }),
            });

            if (response.ok) {
                setStatus('success');
                setEmail('');
            } else {
                const data = await response.json();
                if (data.error === 'ALREADY_SUBSCRIBED') {
                    setStatus('idle');
                    alert(t.alreadySubscribed);
                } else {
                    setStatus('error');
                }
            }
        } catch (err) {
            setStatus('error');
        }
    };

    return (
        <div className="glass-card animate-fade-in" style={{ animationDelay: '0.2s', marginTop: '3rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
                <Mail size={24} className="text-gradient" />
                <h2 style={{ fontSize: '1.5rem' }}>{t.subscribeTitle}</h2>
            </div>

            <p className="text-muted" style={{ marginBottom: '2rem' }}>
                {t.subscribeDesc}
            </p>

            {status === 'success' ? (
                <div style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '1rem',
                    color: '#10b981',
                    padding: '1rem',
                    background: 'rgba(16, 185, 129, 0.1)',
                    borderRadius: '12px'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.875rem' }}>
                        <CheckCircle2 size={20} />
                        <span>{t.success}</span>
                    </div>
                    <button onClick={() => setStatus('idle')} style={{ background: 'transparent', color: 'var(--primary)', border: '1px solid var(--primary)', alignSelf: 'flex-start', padding: '0.4rem 1rem' }}>{t.back}</button>
                </div>
            ) : (
                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <input
                        type="email"
                        placeholder={t.emailPlaceholder}
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                        disabled={status === 'loading'}
                    />

                    {/* Language preference selector */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        <label className="text-muted" style={{ fontSize: '0.875rem', fontWeight: 600 }}>
                            {t.langPreference}
                        </label>
                        <div style={{ display: 'flex', gap: '1rem' }}>
                            {(['zh', 'en'] as const).map((l) => (
                                <label
                                    key={l}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '0.5rem',
                                        cursor: 'pointer',
                                        padding: '0.5rem 1rem',
                                        borderRadius: '8px',
                                        border: `1px solid ${emailLang === l ? 'var(--primary)' : 'var(--border)'}`,
                                        background: emailLang === l ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                                        transition: 'all 0.2s',
                                        fontSize: '0.9rem'
                                    }}
                                >
                                    <input
                                        type="radio"
                                        name="lang"
                                        value={l}
                                        checked={emailLang === l}
                                        onChange={() => setEmailLang(l)}
                                        style={{ accentColor: 'var(--primary)' }}
                                        disabled={status === 'loading'}
                                    />
                                    {l === 'zh' ? t.langZh : t.langEn}
                                </label>
                            ))}
                        </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        <button
                            type="submit"
                            className="btn-primary"
                            disabled={status === 'loading'}
                            style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
                        >
                            {status === 'loading' ? <Loader2 size={18} className="animate-spin" /> : t.subscribeBtn}
                        </button>

                        <div style={{ textAlign: 'center', marginTop: '0.5rem' }}>
                            <span className="text-muted" style={{ fontSize: '0.875rem' }}>{t.noWantMore}</span>
                            <button
                                type="button"
                                disabled={status === 'loading'}
                                onClick={() => {
                                    if (!email || !email.includes('@')) {
                                        alert(t.unsubscribePrompt);
                                        return;
                                    }
                                    window.location.href = `/api/unsubscribe?email=${encodeURIComponent(email)}`;
                                }}
                                style={{ background: 'transparent', color: 'var(--accent)', border: 'none', padding: '0 0.5rem', fontSize: '0.875rem', fontWeight: 600, textDecoration: 'underline' }}
                            >
                                {t.unsubscribeLink}
                            </button>
                        </div>
                    </div>
                    {status === 'error' && (
                        <p style={{ color: 'var(--accent)', fontSize: '0.875rem' }}>{t.error}</p>
                    )}
                </form>
            )}
        </div>
    );
}
