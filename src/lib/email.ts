/**
 * Brevo (formerly Sendinblue) Transactional Email Integration
 * 
 * This service allows sending dynamic emails to any subscriber.
 * It's more suitable for dynamic subscriber lists than Prefect Automations.
 */

export async function sendDailySummary(email: string, title: string, summary_zh: string, summary_en: string, url: string) {
  const BREVO_API_KEY = process.env.BREVO_API_KEY;
  const SENDER_EMAIL = process.env.SENDER_EMAIL || 'daily@arxiv.app';
  const SENDER_NAME = process.env.SENDER_NAME || 'Auto ArXiv';

  if (!BREVO_API_KEY) {
    console.warn('BREVO_API_KEY is missing. Check your .env.local file.');
    return { success: false, error: 'MISSING_BREVO_KEY' };
  }

  const unsubscribeUrl = `${process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000'}/api/unsubscribe?email=${encodeURIComponent(email)}`;

  const emailData = {
    sender: { name: SENDER_NAME, email: SENDER_EMAIL },
    to: [{ email: email }],
    subject: `今日专题: ${title}`,
    htmlContent: `
      <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
        <div style="background: #1a1a1a; padding: 24px; color: white; text-align: center;">
          <h1 style="margin: 0; font-size: 24px;">Auto ArXiv 每日总结</h1>
        </div>
        <div style="padding: 32px; color: #1e293b; line-height: 1.6;">
          <h2 style="margin-top: 0; color: #0f172a;">${title}</h2>
          
          <div style="background: #f8fafc; border-left: 4px solid #3b82f6; padding: 16px; margin: 24px 0;">
            <p style="font-weight: bold; margin-bottom: 8px;">中文摘要 | ZH Summary</p>
            <p style="white-space: pre-wrap; margin: 0;">${summary_zh}</p>
          </div>

          <div style="background: #f8fafc; border-left: 4px solid #94a3b8; padding: 16px; margin: 24px 0;">
            <p style="font-weight: bold; margin-bottom: 8px;">English Summary</p>
            <p style="white-space: pre-wrap; margin: 0;">${summary_en}</p>
          </div>

          <a href="${url}" style="display: inline-block; background: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">查看 arXiv 原文</a>
        </div>
        <div style="background: #f1f5f9; padding: 20px; text-align: center; font-size: 12px; color: #64748b;">
          您收到这封邮件是因为您订阅了 Auto ArXiv。
          <br><br>
          <a href="${unsubscribeUrl}" style="color: #64748b; text-decoration: underline;">退订 / Unsubscribe</a>
        </div>
      </div>
    `
  };

  try {
    const response = await fetch('https://api.brevo.com/v1/smtp/email', {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'api-key': BREVO_API_KEY
      },
      body: JSON.stringify(emailData)
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Brevo API Error:', errorText);
      return { success: false, error: errorText };
    }

    console.log(`Email successfully sent to ${email} via Brevo`);
    return { success: true };
  } catch (err) {
    console.error('Unexpected error sending email via Brevo:', err);
    return { success: false, error: err };
  }
}

// Keep the Prefect event function as an alternative if needed, but renamed
export async function sendPrefectEvent(email: string, title: string, summary_zh: string, summary_en: string, url: string) {
  // Current placeholder, would be same as previous email.ts content
  return { success: true };
}
