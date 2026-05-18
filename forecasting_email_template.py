"""
HTML email template for the Forecasting Digest.
Sections: industry news, recent publications, social media drafts.
"""


def build_forecasting_email(news: dict, pubs: dict, social: dict, date_str: str) -> str:

    # ── News stories ──────────────────────────────────────────────────────────
    stories_html = ""
    for story in news.get("stories", []):
        source = story.get("source", "")
        source_badge = (
            f'<span style="font-size:11px;color:#6b7280;margin-left:8px;">{source}</span>'
            if source else ""
        )
        stories_html += f"""
        <tr><td style="padding:0 0 22px 0;">
          <p style="margin:0 0 4px;font-size:15px;font-weight:600;
                     color:#111827;font-family:Georgia,serif;">
            {story['headline']}{source_badge}
          </p>
          <p style="margin:0;font-size:14px;line-height:1.65;color:#374151;">
            {story['summary']}
          </p>
        </td></tr>"""

    # ── Papers ────────────────────────────────────────────────────────────────
    papers_html = ""
    for paper in pubs.get("papers", []):
        papers_html += f"""
        <tr><td style="padding:0 0 20px 0;">
          <p style="margin:0 0 2px;font-size:14px;font-weight:600;color:#1e293b;">
            {paper['title']}
          </p>
          <p style="margin:0 0 6px;font-size:12px;color:#6b7280;">
            {paper.get('authors','')}&nbsp;·&nbsp;
            <em>{paper.get('venue','')}</em>&nbsp;·&nbsp;
            {paper.get('url_hint','')}
          </p>
          <p style="margin:0;font-size:13px;line-height:1.6;color:#374151;">
            {paper['summary']}
          </p>
        </td></tr>"""

    # ── Social drafts ─────────────────────────────────────────────────────────
    li     = social.get("linkedin", {})
    x_posts = social.get("x_posts", [])

    li_html = f"""
    <tr><td style="padding:0 0 20px 0;">
      <p style="margin:0 0 8px;font-size:12px;font-weight:600;letter-spacing:0.08em;
                 text-transform:uppercase;color:#0a66c2;">LinkedIn</p>
      <div style="background:#f0f7ff;border-left:3px solid #0a66c2;
                  border-radius:0 6px 6px 0;padding:14px 16px;">
        <p style="margin:0;font-size:13px;line-height:1.7;color:#1e293b;
                   white-space:pre-wrap;">{li.get('post','')}</p>
      </div>
    </td></tr>"""

    x_html = ""
    for i, t in enumerate(x_posts, 1):
        x_html += f"""
        <tr><td style="padding:0 0 10px 0;">
          <div style="background:#f0f9ff;border-left:3px solid #000000;
                      border-radius:0 6px 6px 0;padding:12px 16px;">
            <p style="margin:0 0 4px;font-size:11px;font-weight:600;
                       letter-spacing:0.08em;text-transform:uppercase;color:#374151;">
              Post {i} · {len(t.get('text',''))} chars
            </p>
            <p style="margin:0;font-size:13px;line-height:1.6;color:#1e293b;">
              {t.get('text','')}
            </p>
          </div>
        </td></tr>"""

    section = lambda color, label, content: f"""
          <!-- Section header -->
          <tr><td style="padding:24px 40px 4px;">
            <p style="margin:0 0 4px;font-size:10px;font-weight:700;letter-spacing:0.14em;
                       text-transform:uppercase;color:{color};">{label}</p>
            <hr style="border:none;border-top:2px solid {color};margin:0;"/>
          </td></tr>
          <tr><td style="padding:16px 40px 0;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
              {content}
            </table>
          </td></tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Forecasting Digest</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background:#f3f4f6;padding:40px 16px;">
    <tr><td align="center">
      <table width="620" cellpadding="0" cellspacing="0" border="0"
             style="background:#ffffff;border-radius:12px;
                    box-shadow:0 1px 4px rgba(0,0,0,0.08);
                    max-width:620px;width:100%;">

        <!-- Header -->
        <tr><td style="background:#0c2340;border-radius:12px 12px 0 0;padding:32px 40px 28px;">
          <p style="margin:0 0 6px;font-size:11px;letter-spacing:0.14em;
                     text-transform:uppercase;color:#64b5f6;">Saturday Digest</p>
          <h1 style="margin:0;font-size:26px;font-weight:700;color:#f0f9ff;
                      font-family:Georgia,serif;line-height:1.2;">
            Forecasting &amp; Supply Chain
          </h1>
          <p style="margin:8px 0 0;font-size:13px;color:#90a4ae;">{date_str}</p>
        </td></tr>

        <!-- Intro -->
        <tr><td style="padding:28px 40px 0;">
          <p style="margin:0;font-size:16px;line-height:1.7;color:#1e293b;
                     font-style:italic;border-left:3px solid #0c2340;padding-left:16px;">
            {news.get('intro', '')}
          </p>
        </td></tr>

        {section('#0c2340', 'Industry news', stories_html)}

        <!-- What to watch -->
        <tr><td style="padding:4px 40px 8px;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0"
                 style="background:#f0fdf4;border-radius:8px;">
            <tr><td style="padding:14px 18px;">
              <p style="margin:0 0 3px;font-size:10px;font-weight:700;letter-spacing:0.1em;
                         text-transform:uppercase;color:#16a34a;">What to watch</p>
              <p style="margin:0;font-size:13px;line-height:1.6;color:#166534;">
                {news.get('watch','')}
              </p>
            </td></tr>
          </table>
        </td></tr>

        {section('#7c3aed', 'Recent publications', papers_html)}
        {section('#374151', 'Social drafts — ready to post', li_html + x_html)}

        <!-- Footer -->
        <tr><td style="background:#f8fafc;border-radius:0 0 12px 12px;
                        padding:20px 40px;border-top:1px solid #e5e7eb;margin-top:16px;">
          <p style="margin:0;font-size:12px;color:#9ca3af;text-align:center;">
            Powered by Claude + Resend &nbsp;·&nbsp; Delivered every Saturday morning
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""
