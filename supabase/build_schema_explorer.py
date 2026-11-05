"""Bundle the static schema UI as one offline HTML artifact, without live data or credentials."""
import base64
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
frontend = root / "frontend"
admin = frontend / "admin"
css = (frontend / "css/base.css").read_text(encoding="utf-8")

def embed_asset(match):
    path = frontend / match[1].lstrip("/")
    mime = "font/woff2" if path.suffix == ".woff2" else "image/png"
    return 'url("data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode() + '")'

css = re.sub(r'url\("(/assets/[^\"]+)"\)', embed_asset, css)
css += "\n" + (admin / "admin.css").read_text(encoding="utf-8")
scripts = []
for name in ["schema-additions.js", "schema.js", "helpers.js", "dom.js", "schema-views.js"]:
    code = (admin / "js" / name).read_text(encoding="utf-8")
    code = re.sub(r'^import[\s\S]*?from ["\'][^"\']+["\'];\s*', '', code, flags=re.M)
    code = re.sub(r'^export ', '', code, flags=re.M)
    scripts.append(code)
scripts.append('''
const structure = document.getElementById('structure');
const diagram = document.getElementById('diagram');
renderSchemaView(structure);
const diagramView = renderErdView(diagram, {onOpenTable(name) {
  document.querySelector('[data-panel="structure"]').click();
  focusSchemaCard(name);
}});
for (const button of document.querySelectorAll('[data-panel]')) {
  button.addEventListener('click', () => {
    const isDiagram = button.dataset.panel === 'diagram';
    structure.hidden = isDiagram;
    diagram.hidden = !isDiagram;
    if (isDiagram) diagramView.refreshLayout();
    for (const item of document.querySelectorAll('[data-panel]')) {
      item.setAttribute('aria-selected',String(item === button));
    }
  });
}
''')
script = "\n".join(scripts).replace("</script", "<\\/script")
html = '''<!doctype html><html lang="he" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>סכמת מערכת הקייטרינג</title><style>''' + css + '''</style></head><body>
<header class="shell-header"><h1>סכמת מערכת הקייטרינג</h1>
<nav class="view-tabs" role="tablist" aria-label="תצוגת הסכמה">
<button class="btn btn-secondary" data-panel="structure" role="tab" aria-selected="true">טבלאות ועמודות</button>
<button class="btn btn-secondary" data-panel="diagram" role="tab" aria-selected="false">תרשים קשרים</button>
</nav></header><div class="notice notice-warning">מבנה בלבד. הקובץ עצמאי, אינו מתחבר לענן ואינו מכיל נתוני לקוחות או מפתחות גישה.</div>
<main class="shell-main"><section id="structure"></section><section id="diagram" hidden></section></main>
<script type="module">''' + script + '''</script></body></html>'''
output = root / "docs/schema-explorer.html"
output.write_text(html, encoding="utf-8")
print("Generated docs/schema-explorer.html")
