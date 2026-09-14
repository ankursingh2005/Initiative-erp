from pathlib import Path
import re
p = Path('main.py')
s = p.read_text(encoding='utf-8')
start = s.index('    # ---------------- Recommendations')
end = s.index('    return {', s.index('    recommendations.sort', start))
s = s[:start] + '    recommendations = []  # Decision actions are attached by the dashboard endpoint.\n\n' + s[end:]
p.write_text(s, encoding='utf-8')
p = Path('static/analytics.html')
s = p.read_text(encoding='utf-8')
# Replace the radar with a conventional signed bar so margins compare clearly.
s = s.replace("type: 'radar',", "type: 'bar',")
s = s.replace("${k.margin_percent >= 8 ? 'good' : 'bad'}", "${k.margin_percent >= 0 ? 'good' : 'bad'}")
s = s.replace('<th>Profit</th><th>Status</th><th>Review reason</th>', '<th>Profit</th>')
# Keep deeper charts available without dominating the decision overview.
s = s.replace('<div id="statsGrid" class="kpi-grid"></div>', '<details class="card"><summary style="cursor:pointer;font-weight:700">Explore trends, brands and product rankings</summary><p class="sub">Supporting analysis for the current filters.</p><div id="statsGrid" class="kpi-grid"></div>')
s = s.replace('      <div class="card">\n        <h2>Actions supported by your data</h2>', '      </details>\n      <div class="card">\n        <h2>Actions supported by your data</h2>')
p.write_text(s, encoding='utf-8')
scripts = re.findall(r'<script(?:\s[^>]*)?>([\s\S]*?)</script>', s)
Path('tmp/analytics-inline-check.js').write_text('\n'.join(scripts), encoding='utf-8')
