/**
 * Brevo (formerly Sendinblue) Transactional Email Integration
 */

export async function sendDailySummary(
  email: string,
  title: string,
  summary_zh: string,
  summary_en: string,
  url: string,
  language: 'zh' | 'en' = 'zh'
) {
  const BREVO_API_KEY = process.env.BREVO_API_KEY;
  const SENDER_EMAIL = process.env.SENDER_EMAIL || 'daily@arxiv.app';
  const SENDER_NAME = process.env.SENDER_NAME || 'Auto ArXiv';

  if (!BREVO_API_KEY) {
    console.warn('BREVO_API_KEY is missing. Check your .env.local file.');
    return { success: false, error: 'MISSING_BREVO_KEY' };
  }

  const unsubscribeUrl = `${process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000'}/api/unsubscribe?email=${encodeURIComponent(email)}`;

  const isZh = language === 'zh';
  const subject = isZh ? `今日专题: ${title}` : `Today's Paper: ${title}`;
  const summary = isZh ? summary_zh : summary_en;
  const headerLabel = isZh ? 'Auto ArXiv 每日总结' : 'Auto ArXiv Daily Digest';
  const summaryLabel = isZh ? 'AI 摘要' : 'AI Summary';
  const ctaLabel = isZh ? '查看 arXiv 原文 →' : 'Read on arXiv →';
  const siteLabel = isZh ? '访问 Auto ArXiv 网站 →' : 'Visit Auto ArXiv →';
  const siteUrl = process.env.NEXT_PUBLIC_BASE_URL || 'https://arxiv-app-566875806616.us-central1.run.app';
  const footerNote = isZh
    ? '您收到这封邮件是因为您订阅了 Auto ArXiv。'
    : 'You received this email because you subscribed to Auto ArXiv.';
  const unsubLabel = isZh ? '退订' : 'Unsubscribe';

  const emailData = {
    sender: { name: SENDER_NAME, email: SENDER_EMAIL },
    to: [{ email }],
    subject,
    htmlContent: `
      <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
        <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 28px; color: white; text-align: center;">
          <h1 style="margin: 0; font-size: 22px; letter-spacing: 0.5px;">${headerLabel}</h1>
        </div>
        <div style="padding: 32px; color: #1e293b; line-height: 1.7;">
          <h2 style="margin-top: 0; color: #0f172a; font-size: 20px;">${title}</h2>
          <div style="background: #f8fafc; border-left: 4px solid #6366f1; padding: 20px; margin: 24px 0; border-radius: 0 8px 8px 0;">
            <p style="font-weight: 700; margin: 0 0 12px; color: #6366f1; font-size: 13px; text-transform: uppercase; letter-spacing: 1px;">${summaryLabel}</p>
            <p style="white-space: pre-wrap; margin: 0; color: #334155; font-size: 15px;">${summary}</p>
          </div>
          <div style="display: flex; gap: 12px; flex-wrap: wrap; margin-top: 8px;">
            <a href="${url}" style="display: inline-block; background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 14px;">${ctaLabel}</a>
            <a href="${siteUrl}" style="display: inline-block; background: transparent; color: #6366f1; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 14px; border: 2px solid #6366f1;">${siteLabel}</a>
          </div>
        </div>
        <div style="background: #f1f5f9; padding: 20px; text-align: center; font-size: 12px; color: #64748b;">
          ${footerNote}
          <br><br>
          <a href="${unsubscribeUrl}" style="color: #94a3b8; text-decoration: underline;">${unsubLabel}</a>
        </div>
      </div>
    `
  };

  try {
    const response = await fetch('https://api.brevo.com/v3/smtp/email', {
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

    console.log(`Email sent to ${email} [${language}] via Brevo`);
    return { success: true };
  } catch (err) {
    console.error('Unexpected error sending email via Brevo:', err);
    return { success: false, error: err };
  }
}
