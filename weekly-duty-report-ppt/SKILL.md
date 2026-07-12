---
name: weekly-duty-report-ppt
description: Generate the school's weekly duty-report PowerPoint (值周汇报 PPT) from a Word document. Use this skill whenever the user uploads a 值周汇报 .docx, asks to make a 值周 / 值周组 / 值周汇报 PPT, or refers to the four standard sections 亮点工作 / 常规工作 / 问题建议 / 值周反思. The skill applies a pre-built template (blue header bar + colorful ribbon corner mark + 昌平校区 footer), strips numeric prefixes from titles (1.1, 2.3, ...), preserves image aspect ratios, and ensures every image in the doc appears exactly once. Trigger this skill even if the user just sends a .docx that looks like a weekly report — don't wait for them to spell it out.
---

# Weekly Duty-Report PPT (值周汇报)

Turn a 值周汇报 Word document into a polished PPT that matches the established school template (blue header bar, colorful brush-stroke corner mark, campus photo on dividers, no footer by default).

**Always** use the bundled scripts and assets — they encode the exact layout, fonts, colors, and slide order the user has approved. Don't try to rebuild the template from scratch with a different design.

## Inputs

- **Required:** a Word document (`.docx`) with content organized into four sections — 亮点工作, 常规工作, 问题建议 (or the older name 工作建议), 值周反思 (or 值周思考).
- **Inferred:** all images embedded in the doc — they belong to whichever subsection heading immediately precedes them.
- **Ask the user for** these three cover fields if they aren't obvious from prior context:
  - **Cover team list** (e.g. `第四值周组：牛晨蕊、赵成程、李强、秦添、吴雅娜、张杨`)
  - **Cover date** (e.g. `2026.5.5`)
  - **Cover title** — usually you should propose 1–2 candidates yourself based on the report's themes; see `references/conventions.md` for the title pattern.

If the user has run this skill before in the same conversation, reuse their team list and date without re-asking — only the cover title and the doc change week to week.

## Workflow

Do all four steps. Don't skip the visual QA — image overflow and layout glitches are common and the only way to catch them is to look.

### 1. Extract the doc into a plan

```bash
python scripts/extract_docx.py <input.docx> <work_dir>
```

This writes `<work_dir>/plan.json` and copies every image into `<work_dir>/imgs/`. The plan groups paragraphs into 4 sections and splits each section into subsections at every `1.1`-style heading. Image-to-subsection assignment respects document order.

### 2. Edit the plan

Open `plan.json` and do four things:

1. **Fill the cover fields** — `cover_title`, `cover_team`, `cover_date` (replace the `__TODO_*__` placeholders).
2. **Merge or drop empty stragglers.** A subsection like `考务会` with no body and no images is awkward to put on its own slide. Fold it into a neighbor's subtitle (e.g. add "考务会顺利召开，明确监考要求" to the 初一年级家长会 slide) or delete it. Same for any subsection where the title is the entire useful content.
3. **Generate subtitles for image slides without body text.** Read each image (or use the title as a strong hint when you can't see images) and write a one-sentence Chinese subtitle that's specific and plausibly true. Don't invent statistics or names that aren't in the source. See `references/conventions.md` for the subtitle pattern and worked examples.
4. **Clean up titles.** Remove leading numeric prefixes like `1.1`, `2.周三`, `4.5` — the extractor already does this, but double-check. If a title still has stray punctuation (e.g. trailing `。`), trim it. If it's a long sentence rather than a title (the extractor sometimes treats `3.3读书沙龙第一期围炉荐书活动圆满结束。` as the title), shorten it to a real title and move the rest into `body`.

### 3. Build the PPT

```bash
python scripts/build_pptx.py <work_dir>/plan.json <work_dir>/imgs <out.pptx>
```

The script uses the bundled `assets/skeleton.pptx` (cover + TOC + 4 dividers + 感谢聆听) and `assets/ribbon.png` automatically. Every content slide gets a blue header bar with `<num>  <section name>` and the corner ribbon. No footer is added by default — if the user wants one, set `plan["footer"] = "..."` before running the builder.

Image layout is automatic by count: 1 image → centered, 2 → side-by-side, 3 → 3-col. Aspect ratios are always preserved.

### 4. Visual QA — required

```bash
soffice --headless --convert-to pdf <out.pptx> --outdir <work_dir>
pdftoppm -jpeg -r 80 <work_dir>/out.pdf <work_dir>/jpg/slide
```

(Use the bundled `scripts/office/soffice.py` wrapper from the pptx skill if `soffice` isn't on PATH.)

Then **look at the slides**. Check, in this order:

1. Cover — title fits in the blue band, team list reads cleanly.
2. TOC — all four section names visible, no stale labels (工作建议 should read 问题建议; 值周思考 should read 值周反思).
3. Each content slide — title doesn't wrap awkwardly, body subtitle doesn't push images off the bottom, image aspect ratios look right (people aren't stretched), no overlaps.
4. Section dividers (03 / 04 in particular) — confirm they say 问题建议 / 值周反思.

If a single content slide overflows, the usual fix is to **shorten the body** in `plan.json` and rebuild — don't try to fix it by tweaking layout numbers.

### 5. Hand off

Save the final file to the user's outputs folder and present a `computer://` link. If the user previously named the file with a week number / theme (e.g. `2026.5.5第9周值周汇报-严管理稳落实.pptx`), follow the same pattern.

## What's bundled

```
weekly-duty-report-ppt/
├── SKILL.md                       (this file)
├── scripts/
│   ├── extract_docx.py            (.docx → plan.json + imgs/)
│   └── build_pptx.py              (plan.json + imgs/ → .pptx)
├── assets/
│   ├── skeleton.pptx              (7 structural slides w/ placeholders)
│   └── ribbon.png                 (top-right corner mark)
└── references/
    └── conventions.md             (title/subtitle patterns, examples, do/don'ts)
```

## Things to watch

- **Every image must appear exactly once.** The extractor does this by default; if you edit the plan, don't paste the same `imageN.jpeg` into two slides. After building, you can run a quick check: open the .pptx with python-pptx and count distinct `Picture` shapes per slide vs the source.
- **Don't change image aspect ratios.** The builder fits images into boxes preserving ratio — leave the helper alone. If the user wants a tighter crop, use a different image, don't squash.
- **Each image is added once per slide.** The builder doesn't deduplicate — if `plan.json` lists the same image twice it will appear twice. The extractor guarantees uniqueness from the source doc.
- **Section names are fixed.** Cover always lists 亮点工作 · 常规工作 · 问题建议 · 值周反思 (in that order, with those exact characters). The skeleton is wired to those four names; renaming them at runtime would require editing the skeleton.
- **Don't try to update the bundled skeleton casually.** It encodes the cover layout, the TOC icons, the divider photo, and the end card. If a real change is needed (different school, different team), edit `assets/skeleton.pptx` directly in PowerPoint and resave.

For the rationale behind title patterns and example subtitles, read `references/conventions.md`.
