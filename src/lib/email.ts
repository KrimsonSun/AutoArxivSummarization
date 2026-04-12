/**
 * Brevo Transactional Email Integration
 * Renders structured TL;DR + SECTION summaries into email-safe HTML.
 */

// ─── Parser (same logic as PaperDisplay.tsx but produces email-safe HTML) ────

function mdToEmailHtml(text: string): string {
  return text
    // **bold** → <strong>
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // *italic* → <em>
    .replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>')
    // Numbered list "1.  text" or "1. text"
    .replace(/^(\d+)\.\s{1,3}(.+)$/gm, '<div style="margin:4px 0 4px 16px;">$1.&nbsp;$2</div>')
    // Bullet list "* text" or "- text"
    .replace(/^[*\-]\s+(.+)$/gm, '<div style="margin:4px 0 4px 16px;">•&nbsp;$1</div>')
    // Remaining newlines → <br>
    .replace(/\n/g, '<br>');
}

interface EmailSection { title: string; content: string; }

function parseSummaryForEmail(text: string): { tldr: string | null; sections: EmailSection[] } {
  const tldrMatch = text.match(/TL;DR:\s*([\s\S]+?)(?=\n\s*\nSECTION:|\n\s*SECTION:|$)/i);
  const tldr = tldrMatch ? tldrMatch[1].trim() : null;

  const parts = text.split(/\n+SECTION:\s*/);
  const sections: EmailSection[] = [];
  for (let i = 1; i < parts.length; i++) {
    const nl = parts[i].indexOf('\n');
    if (nl === -1) continue;
    const title = parts[i].slice(0, nl).trim();
    const content = parts[i].slice(nl + 1).trim();
    if (title && content) sections.push({ title, content });
  }
  return { tldr, sections };
}

// ─── Build section HTML blocks ─────────────────────────────────────────────

function buildSectionHtml(sections: EmailSection[], isZh: boolean): string {
  if (sections.length === 0) return '';

  const sectionItems = sections.map(sec => `
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:12px;border-radius:8px;overflow:hidden;border:1px solid #e2e8f0;">
          <tr>
            <td style="background:#f0f4ff;padding:8px 16px;border-bottom:1px solid #e2e8f0;">
              <span style="font-size:11px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#6366f1;">${sec.title}</span>
            </td>
          </tr>
          <tr>
            <td style="background:#ffffff;padding:14px 16px;font-size:14px;line-height:1.75;color:#334155;">
              ${mdToEmailHtml(sec.content)}
            </td>
          </tr>
        </table>`).join('');

  return `
        <p style="font-weight:700;margin:24px 0 10px;color:#6366f1;font-size:13px;text-transform:uppercase;letter-spacing:1px;">
          ${isZh ? 'AI 深度解析' : 'AI Deep Analysis'}
        </p>
        ${sectionItems}`;
}

// ─── Main export ───────────────────────────────────────────────────────────

export async function sendDailySummary(
  email: string,
  title: string,
  summary_zh: string,
  summary_en: string,
  url: string,
  language: 'zh' | 'en' = 'zh',
  adjudicatorResult?: any
) {
  const BREVO_API_KEY = process.env.BREVO_API_KEY;
  const SENDER_EMAIL = process.env.SENDER_EMAIL || 'daily@arxiv.app';
  const SENDER_NAME = process.env.SENDER_NAME || 'Auto ArXiv';

  if (!BREVO_API_KEY) {
    console.warn('BREVO_API_KEY is missing.');
    return { success: false, error: 'MISSING_BREVO_KEY' };
  }

  const isZh = language === 'zh';
  const rawSummary = isZh ? summary_zh : summary_en;
  const { tldr, sections } = parseSummaryForEmail(rawSummary);

  const subject = isZh ? `今日专题: ${title}` : `Today's Paper: ${title}`;
  const headerLabel = isZh ? 'Auto ArXiv 每日总结' : 'Auto ArXiv Daily Digest';
  const tldrLabel = isZh ? '一句话总结' : 'TL;DR';
  const ctaLabel = isZh ? '查看 arXiv 原文 →' : 'Read on arXiv →';
  const siteLabel = isZh ? '访问 Auto ArXiv 网站 →' : 'Visit Auto ArXiv →';
  const siteUrl = process.env.NEXT_PUBLIC_BASE_URL || 'https://arxiv-app-566875806616.us-central1.run.app';
  const footerNote = isZh
    ? '您收到这封邮件是因为您订阅了 Auto ArXiv。'
    : 'You received this email because you subscribed to Auto ArXiv.';
  const unsubLabel = isZh ? '退订' : 'Unsubscribe';
  const unsubscribeUrl = `${siteUrl}/api/unsubscribe?email=${encodeURIComponent(email)}`;

  // TL;DR block
  const tldrBlock = tldr ? `
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;border-radius:10px;overflow:hidden;background:linear-gradient(135deg,#ede9fe,#dbeafe);border:1.5px solid #a5b4fc;">
          <tr>
            <td style="padding:4px 16px 0;">
              <span style="font-size:10px;font-weight:800;letter-spacing:0.12em;text-transform:uppercase;color:#6366f1;">⚡ ${tldrLabel}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:6px 16px 14px;font-size:14px;line-height:1.7;font-weight:600;color:#1e1b4b;">
              ${mdToEmailHtml(tldr)}
            </td>
          </tr>
        </table>` : '';

  const sectionsBlock = buildSectionHtml(sections, isZh);

  // Fallback: if no structure parsed, show raw text
  const contentBlock = (tldrBlock || sectionsBlock)
    ? `${tldrBlock}${sectionsBlock}`
    : `<div style="background:#f8fafc;border-left:4px solid #6366f1;padding:20px;border-radius:0 8px 8px 0;">
              <p style="white-space:pre-wrap;margin:0;color:#334155;font-size:14px;line-height:1.75;">${rawSummary.replace(/\n/g, '<br>')}</p>
           </div>`;

  // Build adjudicator block
  let adjudicatorBlock = '';
  if (adjudicatorResult) {
    const adj = adjudicatorResult;
    
    let solutionsHtml = '';
    if (adj.solutions && adj.solutions.length > 0) {
      solutionsHtml = adj.solutions.map((sol: any, idx: number) => {
        let refsHtml = '';
        if (sol.references && sol.references.length > 0) {
           refsHtml = sol.references.map((r: any) => `
             <div style="margin-top:10px;font-size:12px;background:#f8fafc;padding:8px;border-radius:4px;border-left:3px solid #cbd5e1;">
                <strong>${r.title}</strong><br/>
                <span style="color:#64748b;font-style:italic;">"${r.snippet}"</span>
                ${r.recommendation_reason ? `<div style="margin-top:4px;color:#10b981;font-weight:bold;">💡 推荐理由：${r.recommendation_reason}</div>` : ''}
             </div>
           `).join('');
        }
        return `
          <div style="margin-top:12px;padding-bottom:12px;border-bottom:1px dashed #e2e8f0;">
             <div style="font-weight:bold;color:#4f46e5;margin-bottom:4px;">方案 ${idx + 1}: ${sol.direction}</div>
             <div style="font-size:13px;color:#334155;line-height:1.6;">${sol.proposed_method}</div>
             ${refsHtml}
          </div>
        `;
      }).join('');
    }

    adjudicatorBlock = `
        <div style="margin-top:32px;border:1px solid #fecdd3;border-radius:8px;overflow:hidden;background:#fff1f2;">
           <div style="background:#f43f5e;color:#fff;padding:10px 16px;font-weight:bold;font-size:14px;letter-spacing:1px;">
              🔍 批判性分析与破局 (Adjudicator)
           </div>
           <div style="padding:16px;">
              <div style="font-size:14px;color:#9f1239;margin-bottom:8px;">
                 <strong>🚨 逻辑错配诊断：</strong> ${adj.mismatch.mismatch_type} (${adj.mismatch.severity})
              </div>
              <div style="font-size:13px;color:#be123c;margin-bottom:16px;line-height:1.6;">
                 <strong>断裂边：</strong> ${adj.mismatch.broken_edge}<br/>
                 <strong>诊断原因：</strong> ${adj.mismatch.reasoning}
              </div>
              <div style="font-size:14px;color:#4f46e5;font-weight:bold;margin-bottom:8px;border-bottom:2px solid #e0e7ff;padding-bottom:4px;">
                 ✨ 建设性Pinecone破局方案
              </div>
              ${solutionsHtml}
           </div>
        </div>
    `;
  }

  const htmlContent = `
<!DOCTYPE html>
<html lang="${isZh ? 'zh' : 'en'}">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:20px;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:620px;margin:0 auto;">
    <tr>
      <td>
        <!-- Header -->
        <table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:12px 12px 0 0;overflow:hidden;">
          <tr>
            <td style="padding:28px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:22px;letter-spacing:0.5px;">${headerLabel}</h1>
            </td>
          </tr>
        </table>

        <!-- Body -->
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0;padding:0;">
          <tr>
            <td style="padding:28px 32px 24px;">
              <h2 style="margin:0 0 20px;color:#0f172a;font-size:19px;line-height:1.4;">${title}</h2>

              ${contentBlock}
              
              ${adjudicatorBlock}

              <!-- CTAs -->
              <table cellpadding="0" cellspacing="0" style="margin-top:20px;">
                <tr>
                  <td style="padding-right:10px;">
                    <a href="${url}" style="display:inline-block;background:#6366f1;color:#ffffff;padding:11px 22px;text-decoration:none;border-radius:8px;font-weight:700;font-size:14px;">${ctaLabel}</a>
                  </td>
                  <td>
                    <a href="${siteUrl}" style="display:inline-block;background:transparent;color:#6366f1;padding:11px 22px;text-decoration:none;border-radius:8px;font-weight:700;font-size:14px;border:2px solid #6366f1;">${siteLabel}</a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>

        <!-- Footer -->
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;">
          <tr>
            <td style="padding:18px 32px;text-align:center;font-size:12px;color:#64748b;">
              ${footerNote}<br><br>
              <a href="${unsubscribeUrl}" style="color:#94a3b8;text-decoration:underline;">${unsubLabel}</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>`;

  try {
    const response = await fetch('https://api.brevo.com/v3/smtp/email', {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'api-key': BREVO_API_KEY,
      },
      body: JSON.stringify({
        sender: { name: SENDER_NAME, email: SENDER_EMAIL },
        to: [{ email }],
        subject,
        htmlContent,
      }),
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
