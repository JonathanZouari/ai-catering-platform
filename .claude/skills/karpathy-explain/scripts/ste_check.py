"""Readability lint in the spirit of ASD-STE100. Not a certification.

Usage: python ste_check.py [file]   (reads stdin when no file is given)
Limits: 25 words per descriptive sentence, 20 per procedure (imperative) sentence.
"""

import re
import sys

DESCRIPTIVE_LIMIT = 25
PROCEDURE_LIMIT = 20
# English imperative verbs that usually start a procedure step.
STEP_VERBS = {
    "add", "apply", "check", "choose", "close", "connect", "copy", "create", "delete", "enter",
    "install", "make", "open", "press", "remove", "replace", "run", "select", "set", "start",
    "stop", "turn", "use", "verify", "write",
}
PASSIVE = re.compile(r"\b(is|are|was|were|be|been|being)\s+(\w+ed|\w+en)\b", re.IGNORECASE)


def sentences(text: str) -> list[str]:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)  # skip code blocks
    parts = re.split(r"(?<=[.!?])\s+|\n{2,}|\n[-*]\s+", text)
    return [p.strip() for p in parts if len(p.split()) > 1]


def main() -> None:
    text = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else sys.stdin.read()
    sents = sentences(text)
    if not sents:
        print("No sentences found.")
        return
    counts = [len(s.split()) for s in sents]
    over, passive = [], []
    for s, n in zip(sents, counts, strict=True):
        first = re.sub(r"\W", "", s.split()[0]).lower()
        limit = PROCEDURE_LIMIT if first in STEP_VERBS else DESCRIPTIVE_LIMIT
        if n > limit:
            over.append((n, limit, s))
        if PASSIVE.search(s):
            passive.append(s)
    print(f"sentences: {len(sents)}")
    print(f"average words: {sum(counts) / len(counts):.1f}   longest: {max(counts)}")
    print(f"over the limit ({PROCEDURE_LIMIT} procedure / {DESCRIPTIVE_LIMIT} descriptive): {len(over)}")
    for n, limit, s in over[:10]:
        print(f"  [{n}>{limit}] {s[:100]}")
    print(f"possible passive voice: {len(passive)}")
    for s in passive[:10]:
        print(f"  {s[:100]}")
    print("Lint only. Keep every fact, number and caveat from the source.")


if __name__ == "__main__":
    main()
