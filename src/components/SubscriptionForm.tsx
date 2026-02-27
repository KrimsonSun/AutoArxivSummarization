'use client';

import { useState } from 'react';
import { Mail, Loader2, CheckCircle2 } from 'lucide-react';

export default function SubscriptionForm() {
    const [email, setEmail] = useState('');
    const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setStatus('loading');

        try {
            const response = await fetch('/api/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email }),
            });

            if (response.ok) {
                setStatus('success');
                setEmail('');
            } else {
                const data = await response.json();
                if (data.error === 'ALREADY_SUBSCRIBED') {
                    setStatus('idle');
                    alert('您已订阅，请勿重复操作！');
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
                <h2 style={{ fontSize: '1.5rem' }}>订阅每日摘要</h2>
            </div>

            <p className="text-muted" style={{ marginBottom: '2rem' }}>
                我们将每天把最新的 CS 论文精选发送到您的邮箱。不再错过任何重磅研究。
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
                        <span>操作成功！</span>
                    </div>
                    <button onClick={() => setStatus('idle')} style={{ background: 'transparent', color: 'var(--primary)', border: '1px solid var(--primary)', alignSelf: 'flex-start', padding: '0.4rem 1rem' }}>返回</button>
                </div>
            ) : (
                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <input
                        type="email"
                        placeholder="your@email.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                        disabled={status === 'loading'}
                    />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        <button
                            type="submit"
                            className="btn-primary"
                            disabled={status === 'loading'}
                            style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
                        >
                            {status === 'loading' ? <Loader2 size={18} className="animate-spin" /> : '立即订阅'}
                        </button>

                        <div style={{ textAlign: 'center', marginTop: '0.5rem' }}>
                            <span className="text-muted" style={{ fontSize: '0.875rem' }}>不再感兴趣？</span>
                            <button
                                type="button"
                                disabled={status === 'loading'}
                                onClick={async () => {
                                    if (!email || !email.includes('@')) {
                                        alert('请输入您想退订的邮箱地址');
                                        return;
                                    }
                                    window.location.href = `/api/unsubscribe?email=${encodeURIComponent(email)}`;
                                }}
                                style={{ background: 'transparent', color: 'var(--accent)', border: 'none', padding: '0 0.5rem', fontSize: '0.875rem', fontWeight: 600, textDecoration: 'underline' }}
                            >
                                点击此处退订
                            </button>
                        </div>
                    </div>
                    {status === 'error' && (
                        <p style={{ color: 'var(--accent)', fontSize: '0.875rem' }}>出错了，请稍后再试。</p>
                    )}
                </form>
            )}
        </div>
    );
}
