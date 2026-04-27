"""
HTML email template for the AI News Digest.
Clean, email-client-safe inline CSS.
"""


def build_html_email(digest: dict, date_str: str) -> str:
    stories_html = ""
    for story in digest["stories"]:
        links_html = ""
        links = story.get("links") or []
        if isinstance(links, str):
            links = [links]
        if isinstance(links, list) and links:
            link_items = ""
            for url in links:
                if not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")):
                    continue
                link_items += (
                    f'<a href="{url}" '
                    'style="color:#2563eb;text-decoration:underline;" target="_blank" rel="noopener noreferrer">'
                    "Verify</a>"
                )
                link_items += '<span style="color:#cbd5e1;">&nbsp;·&nbsp;</span>'

            if link_items.endswith('<span style="color:#cbd5e1;">&nbsp;·&nbsp;</span>'):
                link_items = link_items[: -len('<span style="color:#cbd5e1;">&nbsp;·&nbsp;</span>')]

            if link_items:
                links_html = f"""
            <p style="margin:10px 0 0;font-size:13px;line-height:1.6;color:#64748b;">
              {link_items}
            </p>"""

        stories_html += f"""
        <tr>
          <td style="padding:0 0 24px 0;">
            <p style="margin:0 0 6px 0;font-size:16px;font-weight:600;
                       color:#111827;font-family:Georgia,serif;">
              {story['headline']}
            </p>
            <p style="margin:0;font-size:15px;line-height:1.65;color:#374151;">
              {story['summary']}
            </p>
            {links_html}
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Weekly AI Digest</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,
             BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">

  <!-- Wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background:#f3f4f6;padding:40px 16px;">
    <tr>
      <td align="center">
        <!-- Card -->
        <table width="600" cellpadding="0" cellspacing="0" border="0"
               style="background:#ffffff;border-radius:12px;
                      box-shadow:0 1px 4px rgba(0,0,0,0.08);
                      max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background:#0f172a;border-radius:12px 12px 0 0;
                        padding:32px 40px 28px;">
              <p style="margin:0 0 6px 0;font-size:11px;letter-spacing:0.12em;
                         text-transform:uppercase;color:#94a3b8;">
                Weekly Digest
              </p>
              <h1 style="margin:0;font-size:26px;font-weight:700;color:#f8fafc;
                          font-family:Georgia,serif;line-height:1.2;">
                AI News Digest
              </h1>
              <p style="margin:8px 0 0;font-size:13px;color:#64748b;">{date_str}</p>
            </td>
          </tr>

          <!-- Intro -->
          <tr>
            <td style="padding:32px 40px 0;">
              <p style="margin:0;font-size:16px;line-height:1.7;color:#1e293b;
                         font-style:italic;border-left:3px solid #6366f1;
                         padding-left:16px;">
                {digest['intro']}
              </p>
            </td>
          </tr>

          <!-- Divider -->
          <tr>
            <td style="padding:24px 40px 16px;">
              <hr style="border:none;border-top:1px solid #e5e7eb;margin:0;"/>
            </td>
          </tr>

          <!-- Stories -->
          <tr>
            <td style="padding:0 40px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                {stories_html}
              </table>
            </td>
          </tr>

          <!-- What to Watch -->
          <tr>
            <td style="padding:0 40px 32px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0"
                     style="background:#eff6ff;border-radius:8px;">
                <tr>
                  <td style="padding:16px 20px;">
                    <p style="margin:0 0 4px;font-size:11px;font-weight:600;
                               letter-spacing:0.1em;text-transform:uppercase;
                               color:#3b82f6;">
                      What to watch
                    </p>
                    <p style="margin:0;font-size:14px;line-height:1.6;color:#1e40af;">
                      {digest['watch']}
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f8fafc;border-radius:0 0 12px 12px;
                        padding:20px 40px;border-top:1px solid #e5e7eb;">
              <p style="margin:0;font-size:12px;color:#9ca3af;text-align:center;">
                Powered by Claude + Resend &nbsp;·&nbsp;
                Delivered every Sunday morning
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""
