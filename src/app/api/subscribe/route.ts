import { NextResponse } from 'next/server';
import { dbOps } from '@/lib/db';

export async function POST(request: Request) {
    try {
        const { email, language } = await request.json();

        if (!email || !email.includes('@')) {
            return NextResponse.json({ error: 'Invalid email address' }, { status: 400 });
        }

        const lang: 'zh' | 'en' = language === 'en' ? 'en' : 'zh';

        if (await dbOps.isSubscriberExists(email)) {
            // Update language preference even if already subscribed
            await dbOps.addSubscriber(email, lang);
            return NextResponse.json({ error: 'ALREADY_SUBSCRIBED' }, { status: 400 });
        }

        await dbOps.addSubscriber(email, lang);

        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('Subscription failed:', error);
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
    }
}
