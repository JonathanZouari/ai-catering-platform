---
name: karpathy-explain
description: Make AI output easy to understand and verify, using Andrej Karpathy's four ways to read model output - simplified technical English (ASD-STE100), diagrams, interactive HTML pages, and explainer videos. Use when the user asks to explain something clearly or simply, "write like an aircraft manual", turn an answer into a diagram, a self-contained interactive page or a video, or lint/measure how readable a text is.
---

# Karpathy explain

Karpathy's point: as models write more, the bottleneck is the human's time to understand and check the output. So change the *form* of the output. Pick the lightest of four forms that does the job, then check it against the source.

Source note: this skill follows secondary write-ups of Karpathy's post. The Medium article that inspired it (and its browser measuring tool) could not be fetched, so the measurable limits below come from those summaries and from ASD-STE100. Treat them as defaults, not as quotes.

## Pick the form

| Form | Use when | Cost |
| --- | --- | --- |
| 1. Simplified technical English | Reading fast and being sure: a clause, an error message, an abstract, a spec | Lowest |
| 2. Diagram | The answer has steps, parts, branches or hand-offs | Low |
| 3. Interactive HTML page | The user wants to try "what if I change this input" | Medium |
| 4. Explainer video | Learning a topic from scratch, or teaching a team | Highest |

Start at 1. Move up only when the content is a flow (2), has variables to play with (3), or needs a narrated walkthrough (4). Say which form you chose and why in one line.

## 1. Simplified technical English (ASD-STE100 style)

Write as an aircraft maintenance manual does:

- One idea per sentence. Short sentences.
- Procedure sentences: 20 words or fewer. Descriptive sentences: 25 words or fewer.
- Active voice. Imperative for steps ("Close the valve.").
- One word, one meaning. Do not swap synonyms for variety. Keep the exact technical terms from the source.
- No filler, no figures of speech, no stacked noun strings.
- Put warnings and cautions before the step they apply to.
- Aim for about 80% of strict STE. Strict STE drops facts, especially in code and legal text.

**Never drop** facts, numbers, units, names, conditions or caveats. If a rule would remove one, keep the fact and break the rule. After rewriting, compare against the source and list anything you had to leave out.

Measure it: `python .claude/skills/karpathy-explain/scripts/ste_check.py <file>` (or pipe text on stdin). It reports sentence count, average and longest sentence, sentences over the limit, and likely passive voice. It is a lint, not a certification: there is no approved-word dictionary check.

Hebrew: STE is an English standard. For Hebrew apply the same spirit (short sentences, one idea each, active voice, fixed terms). The checker's word limits still work as a rough guide; its passive-voice check is English only.

## 2. Diagram

- Output Mermaid code (a `flowchart`) and, when the user can see it, a one-line caption per section. Boxes are steps, arrows are hand-offs, diamonds are decisions.
- Include only steps that appear in the source. Do not invent a step to make the flow look complete.
- Check every arrow against the source. A clean diagram can be wrong.
- If the user needs a file or a page, use the Artifact tool and the artifact-diagramming skill instead of raw Mermaid.

## 3. Interactive HTML page

- One self-contained file. No external libraries, no network calls.
- One interactive element that shows what changes when an input changes (slider, toggle, step-through button).
- All page text in simple technical English (section 1). RTL and Hebrew when the user works in Hebrew.
- Compute displayed numbers from the same formula you state in the page. Say the formula. The user must be able to check the numbers.
- Never ask the user to type private data into a page, and warn them not to do that with pages they did not build.
- Publish through the Artifact tool when the user wants to open or share it.

## 4. Explainer video

Slowest to build and easiest to over-trust. Only when asked or clearly worth it.

- Narrow topic, under three minutes.
- Write the script first and get approval before rendering.
- Render a low-quality preview first, then the final version.
- Style: 3Blue1Brown-like, built with the Manim Community Edition.
- Narration with text-to-speech. Read any API key from an environment variable. Never ask the user to paste a key into chat and never write one into a file. With no key, use a free local text-to-speech tool.

## Verify (every form)

1. Re-read the source and the output side by side.
2. List facts, numbers and caveats from the source. Confirm each one is still present.
3. For diagrams and pages: confirm each arrow, number and branch against the source.
4. State what you simplified and what you left out. Do not claim the output is certified STE.
