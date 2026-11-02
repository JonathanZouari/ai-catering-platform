"""Sync repo docs and the git commit log into the Obsidian vault project folder.

Run by the Stop hook in .claude/settings.local.json. Stdlib only, idempotent:
files are rewritten only when their content changed. The hub note is hand-edited
in the vault and never touched here.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VAULT = Path(
    os.environ.get("OBSIDIAN_PROJECT_DIR", r"C:\Obsidian_Vault\פלטפורמת קייטרינג AI")
)


def write_if_changed(path: Path, text: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def commit_log() -> str:
    out = subprocess.run(
        ["git", "log", "--all", "--date=short", "--format=%ad\t%h\t%D\t%s"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    lines = ["# יומן commits", "", "נוצר אוטומטית מ-git (`tools/obsidian_sync.py`). לא לערוך ידנית.", ""]
    lines += ["| תאריך | commit | refs | הודעה |", "|---|---|---|---|"]
    for row in out.splitlines():
        date, sha, refs, subject = row.split("\t", 3)
        lines.append(f"| {date} | `{sha}` | {refs} | {subject.replace('|', '\\|')} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    if not VAULT.is_dir():
        return 0  # no vault on this machine (e.g. cloud session)
    changed = [
        str(md.relative_to(REPO))
        for md in sorted((REPO / "docs").rglob("*.md"))
        if write_if_changed(VAULT / md.relative_to(REPO), md.read_text(encoding="utf-8"))
    ]
    if write_if_changed(VAULT / "יומן commits.md", commit_log()):
        changed.append("יומן commits.md")
    if changed:
        print(f"Obsidian sync: {len(changed)} file(s) updated", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
