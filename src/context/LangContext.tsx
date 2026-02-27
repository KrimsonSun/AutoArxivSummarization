'use client';

import { createContext, useContext, useState, ReactNode } from 'react';

type Lang = 'zh' | 'en';

interface LangContextType {
    lang: Lang;
    setLang: (l: Lang) => void;
    t: typeof translations['zh'];
}

export const translations = {
    zh: {
        // Header
        tagline: '每日从 CS 论文海中捞一根针，AI 为您深度解析。',
        // Paper card
        todaySelection: '今日精选',
        aiSummary: 'AI 深度解析',
        readOriginal: '阅读原文',
        authors: '作者',
        date: '发布日期',
        toggleLang: 'Switch to English',
        noPaper: '今天还没有爬取论文，请稍后再来。',
        // Subscription form
        subscribeTitle: '订阅每日摘要',
        subscribeDesc: '我们将每天把最新的 CS 论文精选发送到您的邮箱。不再错过任何重磅研究。',
        emailPlaceholder: 'your@email.com',
        subscribeBtn: '立即订阅',
        unsubscribeLink: '点击此处退订',
        unsubscribePrompt: '请输入您想退订的邮箱地址',
        alreadySubscribed: '您已订阅，请勿重复操作！',
        error: '出错了，请稍后再试。',
        success: '操作成功！',
        back: '返回',
        langPreference: '邮件语言偏好',
        langZh: '中文摘要',
        langEn: 'English',
        noWantMore: '不再感兴趣？',
        // Footer
        footer: `© ${new Date().getFullYear()} Auto ArXiv. Built with Next.js & Gemini 2.5 Flash.`,
    },
    en: {
        tagline: 'One CS paper a day, deeply analyzed by AI. Stay sharp, effortlessly.',
        todaySelection: "Today's Pick",
        aiSummary: 'AI Deep Analysis',
        readOriginal: 'Read Paper',
        authors: 'Authors',
        date: 'Published',
        toggleLang: '切换至中文',
        noPaper: "No paper fetched today yet. Check back later.",
        subscribeTitle: 'Subscribe to Daily Digest',
        subscribeDesc: "Get the latest CS paper highlights delivered to your inbox every day. Never miss a breakthrough.",
        emailPlaceholder: 'your@email.com',
        subscribeBtn: 'Subscribe Now',
        unsubscribeLink: 'Unsubscribe here',
        unsubscribePrompt: 'Enter the email address you want to unsubscribe.',
        alreadySubscribed: 'You are already subscribed!',
        error: 'Something went wrong. Please try again later.',
        success: 'Done!',
        back: 'Go back',
        langPreference: 'Email Language Preference',
        langZh: '中文 (Chinese)',
        langEn: 'English',
        noWantMore: 'Not interested anymore?',
        footer: `© ${new Date().getFullYear()} Auto ArXiv. Built with Next.js & Gemini 2.5 Flash.`,
    },
};

const LangContext = createContext<LangContextType | null>(null);

export function LangProvider({ children }: { children: ReactNode }) {
    const [lang, setLang] = useState<Lang>('zh');
    return (
        <LangContext.Provider value={{ lang, setLang, t: translations[lang] }}>
            {children}
        </LangContext.Provider>
    );
}

export function useLang() {
    const ctx = useContext(LangContext);
    if (!ctx) throw new Error('useLang must be used within a LangProvider');
    return ctx;
}
