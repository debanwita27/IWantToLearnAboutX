"""
emailer.py — HTML email delivery via Resend for dm-plus

Sends the daily knowledge digest email at 9:05 AM IST.
"""

import os
import logging
import re
import markdown

import resend

from synthesizer import DailyDigest

log = logging.getLogger(__name__)

DEPTH_TAG_COLORS = {
    "surface": "#6B7280",
    "mid": "#2563EB",
    "deep": "#7C3AED",
    "rabbit_hole": "#DC2626",
}

DEPTH_TAG_LABELS = {
    "surface": "surface",
    "mid": "mid",
    "deep": "deep",
    "rabbit_hole": "rabbit hole",
}


def _progress_bar_html(day: int, total: int = 7) -> str:
    filled = "█" * day
    empty = "░" * (total - day)
    pct = int((day / total) * 100)
    return f"""
    <div style="font-family:monospace;font-size:13px;color:#6B7280;margin:8px 0;">
      {filled}{empty} {pct}%
    </div>"""


def _depth_badge(tag: str) -> str:
    color = DEPTH_TAG_COLORS.get(tag, "#6B7280")
    label = DEPTH_TAG_LABELS.get(tag, tag)
    return (
        f'<span style="background:{color};color:#fff;font-size:10px;font-weight:600;'
        f'padding:2px 7px;border-radius:10px;letter-spacing:0.5px;text-transform:uppercase;">'
        f"{label}</span>"
    )


def _render_links(links: list[dict]) -> str:
    if not links:
        return ""
    items = []
    for link in links:
        badge = _depth_badge(link.get("depth_tag", "mid"))
        title = link.get("title", "")
        url = link.get("url", "#")
        why = link.get("why", "")
        items.append(f"""
        <li style="margin-bottom:14px;list-style:none;padding-left:0;">
          <div style="margin-bottom:4px;">{badge}</div>
          <a href="{url}" style="color:#1d1d1f;font-weight:600;font-size:15px;
             text-decoration:none;border-bottom:1px solid #d1d5db;">{title}</a>
          {f'<p style="margin:4px 0 0;color:#6B7280;font-size:13px;">{why}</p>' if why else ""}
        </li>""")
    return "<ul style='padding:0;margin:0;'>" + "".join(items) + "</ul>"


def _nudget_to_html(nugget: str) -> str:
    return markdown.markdown(nugget, extensions=["extra", "nl2br"])


def build_html(digest: DailyDigest) -> str:
    nugget_html = _nudget_to_html(digest.nugget)
    links_html = _render_links(digest.curated_links)
    ref_html = _nudget_to_html(digest.reference_pick)
    bar_html = _progress_bar_html(digest.day)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>dm-plus · {digest.topic_name} · Day {digest.day}</title>
</head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:640px;margin:0 auto;padding:32px 16px;">

    <!-- Header -->
    <div style="border-bottom:2px solid #1d1d1f;padding-bottom:20px;margin-bottom:28px;">
      <div style="font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;
                  color:#6B7280;margin-bottom:8px;">dm-plus · {digest.week}</div>
      <h1 style="margin:0 0 8px;font-size:26px;font-weight:800;color:#1d1d1f;line-height:1.2;">
        {digest.topic_name}
      </h1>
      <div style="font-size:13px;color:#6B7280;margin-bottom:12px;">
        Day {digest.day}/7 · {digest.progress_bar.split("·")[2].strip().replace("-"," ")}
      </div>
      {bar_html}
      <div style="font-size:12px;color:#9CA3AF;margin-top:6px;font-style:italic;">
        {_get_focus_label(digest.day, digest.progress_bar)}
      </div>
    </div>

    <!-- Main Nugget -->
    <div style="margin-bottom:36px;line-height:1.75;color:#1d1d1f;font-size:16px;">
      {nugget_html}
    </div>

    <!-- Curated Links -->
    {'<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:24px;margin-bottom:28px;"><h2 style="margin:0 0 18px;font-size:16px;font-weight:700;color:#1d1d1f;letter-spacing:-0.3px;">Today\'s Reading</h2>' + links_html + '</div>' if links_html else ""}

    <!-- Reference Pick -->
    <div style="background:#1d1d1f;color:#fff;border-radius:12px;padding:24px;margin-bottom:28px;">
      <div style="font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;
                  color:#9CA3AF;margin-bottom:12px;">Today's Reference Pick</div>
      <div style="font-size:14px;line-height:1.65;color:#f3f4f6;">
        {ref_html}
      </div>
    </div>

    <!-- Footer -->
    <div style="border-top:1px solid #e5e7eb;padding-top:20px;text-align:center;">
      <div style="font-size:12px;color:#9CA3AF;margin-bottom:6px;">
        dm-plus · a plus version of yourself, one week at a time
      </div>
      <div style="font-size:11px;color:#D1D5DB;">
        Week {digest.week} · {digest.topic_name}
      </div>
    </div>

  </div>
</body>
</html>"""


def _get_focus_label(day: int, progress_bar: str) -> str:
    is_depth = "depth-first" in progress_bar
    labels_depth = {
        1: "Mental model + stack placement",
        2: "Internal mechanics",
        3: "Failure modes & tradeoffs",
        4: "Production war stories",
        5: "Source walkthroughs",
        6: "Academic lineage",
        7: "Synthesis + open problems",
    }
    labels_breadth = {
        1: "Overview",
        2: "Historical roots",
        3: "Core mechanics",
        4: "Controversies & edge cases",
        5: "Rabbit hole",
        6: "Applications",
        7: "Synthesis",
    }
    labels = labels_depth if is_depth else labels_breadth
    return labels.get(day, "")


def build_plaintext(digest: DailyDigest) -> str:
    lines = [
        f"dm-plus · {digest.week}",
        f"{digest.topic_name} · Day {digest.day}/7",
        "=" * 60,
        "",
        digest.nugget,
        "",
        "TODAY'S READING",
        "-" * 40,
    ]
    for link in digest.curated_links:
        lines.append(f"[{link.get('depth_tag','').upper()}] {link.get('title','')}")
        lines.append(f"  {link.get('url','')}")
        if link.get("why"):
            lines.append(f"  → {link['why']}")
        lines.append("")
    lines += [
        "TODAY'S REFERENCE PICK",
        "-" * 40,
        digest.reference_pick,
        "",
        "—",
        "dm-plus · a plus version of yourself, one week at a time",
    ]
    return "\n".join(lines)


def send(digest: DailyDigest) -> bool:
    resend.api_key = os.environ.get("RESEND_API_KEY", "")
    to_email = os.environ.get("EMAIL_TO", "")

    if not resend.api_key:
        raise EnvironmentError("RESEND_API_KEY is not set")
    if not to_email:
        raise EnvironmentError("EMAIL_TO is not set")

    subject = f"[dm-plus] Day {digest.day}/7 · {digest.topic_name}"
    html = build_html(digest)
    text = build_plaintext(digest)

    try:
        params: resend.Emails.SendParams = {
            "from": "dm-plus <learning@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "html": html,
            "text": text,
        }
        response = resend.Emails.send(params)
        log.info(f"Email sent successfully. ID: {response.get('id', 'unknown')}")
        return True
    except Exception as e:
        log.error(f"Failed to send email: {e}")
        raise


def save_artifact(digest: DailyDigest, output_dir: str = "output/research") -> str:
    """Save the raw research bundle + digest as a markdown artifact for the week's branch."""
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"day-{digest.day}.md")
    with open(filename, "w") as f:
        f.write(f"# {digest.topic_name} — Day {digest.day}/7\n\n")
        f.write(f"**Week:** {digest.week}  \n")
        f.write(f"**Progress:** {digest.progress_bar}  \n\n")
        f.write("---\n\n")
        f.write("## Today's Digest\n\n")
        f.write(digest.nugget + "\n\n")
        f.write("---\n\n")
        f.write("## Curated Links\n\n")
        for link in digest.curated_links:
            f.write(f"- **[{link.get('depth_tag','').upper()}]** [{link.get('title','')}]({link.get('url','')})")
            if link.get("why"):
                f.write(f"  \n  *{link['why']}*")
            f.write("\n")
        f.write("\n---\n\n")
        f.write("## Reference Pick\n\n")
        f.write(digest.reference_pick + "\n\n")
        f.write("---\n\n")
        f.write("## Raw Research Context\n\n")
        f.write("```\n")
        f.write(digest.raw_bundle_context[:3000])
        f.write("\n```\n")
    log.info(f"Artifact saved: {filename}")
    return filename
