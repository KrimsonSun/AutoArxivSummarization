import { NextResponse } from 'next/server';
import { dbOps } from '@/lib/db';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const email = searchParams.get('email');

  if (!email) {
    return NextResponse.json({ error: 'Missing email' }, { status: 400 });
  }

  try {
    await dbOps.removeSubscriber(email);
    // Return a simple HTML page confirming the unsubscription
    return new Response(
      `
      <html>
        <body style="font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh;">
          <div style="text-align: center; padding: 2rem; border-radius: 12px; background: #f9f9f9;">
            <h1 style="color: #333;">退订成功</h1>
            <p>您的邮箱 ${email} 已从我们的列表中移除。</p>
            <a href="/" style="color: #0070f3;">返回主页</a>
          </div>
        </body>
      </html>
      `,
      { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
    );
  } catch (error) {
    console.error('Unsubscribe failed:', error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
