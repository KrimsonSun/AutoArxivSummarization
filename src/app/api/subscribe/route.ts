import { NextResponse } from 'next/server';
import { dbOps } from '@/lib/db';

export async function POST(request: Request) {
    try {
        const { email } = await request.json();

        if (!email || !email.includes('@')) {
            return NextResponse.json({ error: 'Invalid email address' }, { status: 400 });
        }

        if (dbOps.isSubscriberExists(email)) {
            return NextResponse.json({ error: 'ALREADY_SUBSCRIBED' }, { status: 400 });
        }

        dbOps.addSubscriber(email);

        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('Subscription failed:', error);
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
    }
}
