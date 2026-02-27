'use client';

import { LangProvider } from '@/context/LangContext';
import { ReactNode } from 'react';

export default function PageWrapper({ children }: { children: ReactNode }) {
    return <LangProvider>{children}</LangProvider>;
}
