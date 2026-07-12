# Conventions for the Weekly Value-Report PPT

Read this whenever you're writing a cover title or subtitle for this skill. The patterns below are what the user has already accepted on prior weeks — staying consistent matters more than being clever.

## Cover title

Two parallel four-character (or 5-character) phrases joined by a comma. ~12–15 characters total. Each phrase typically follows a `严X` / `重X` / `育X` verb pattern and ends with a result noun (`落实`, `成长`, `常规`).

The title should distill the report's emphasis — what the value group focused on this week.

**Worked examples (real prior weeks):**
- `敬畏重复坚守细节` (Week 8 — single 8-char phrase variant)
- `以坚持筑底色，让值周见成长` (one of the templates)
- `严管理稳落实，重训练促成长` (Week 9 — chosen for a week heavy on exam-prep, drills, and reflection on strict management)

**Pattern templates (pick whichever fits the week):**
- `严X理X落实，重X练X成长`
- `抓X重X筑常规，育X促长向未来`
- `以X理筑底色，以X落实育成长`

When proposing a title, look at the 值周反思 section first — it usually telegraphs the theme. For a week with three reflections like "严格管理，稳抓落实 / 营造成长的环境 / 行为训练，刻意练习", the title should echo *management + training + growth*.

**Don't** propose generic titles like `本周工作汇报` or `值周回顾`. They're not wrong, but the user wants the title to actually say something about the week.

## Subtitle (one-paragraph body for image slides)

When a subsection has images but the doc gave no explanatory paragraph, write a 1–2 sentence Chinese subtitle.

**Rules:**
- Specific, not generic. "组织开展教师会议" is filler. "围绕评教数据反馈、巡课反馈、工作提示三大议题展开研讨" tells the reader what actually happened.
- Tied to image content when possible. If an image clearly shows a screen captioned `转换好心态 · 专注迎高考`, weave that exact phrase in — it makes the subtitle feel observed rather than guessed.
- Don't invent specific facts (named people, specific numbers, schools by name) that aren't in the source. Generalize when in doubt.
- Echo the title's verb, don't just paraphrase it. If the title is `跨校党建调研`, the subtitle should add the *what / how / why*, not restate "跨校党建调研活动顺利开展".
- Length: roughly 30–60 characters. Long enough to feel substantial, short enough to fit one line above the images.

**Worked examples (from Week 9):**

| Title | Subtitle |
|------|---------|
| 高三年级化学专家讲座 | 化学学科专家走进校园开讲座，聚焦高考核心考点与解题思路，学生认真听讲、踊跃互动，为冲刺备考再添助力。 |
| 高一年级教师会 | 围绕评教数据反馈、巡课反馈、工作提示三大议题展开研讨，回看教学情况、明确下阶段重点。 |
| 跨校党建调研 | 兄弟校区莅临交流党建工作，双方围绕组织建设与活动开展深入座谈，互学互鉴共促党建提质增效。 |
| 高三年级学生会与心理讲座 | 高三学生大会与心理讲座同步开展，以"转换好心态 · 专注迎高考"为主题，帮助学生稳心态、提状态、迎冲刺。 |
| 高一英语活动 | 年级组织英语词王争霸赛，学生登台同台比拼，营造浓厚学科氛围，激发学习兴趣与表达自信。 |

Notice how the 高一英语活动 subtitle names "词王争霸赛" — that's because the picture clearly shows that event's stage backdrop. Always look at the image before writing.

## Title cleanup

The doc usually writes titles as `1.1高三年级化学专家讲座` — strip the leading number. The extractor does this with a regex; double-check edge cases like:

- `4.5初三着重分析本次一模成绩` → `初三一模分析家长会` (also worth shortening — see below)
- `3.3读书沙龙第一期围炉荐书活动圆满结束。` → title becomes `读书沙龙·围炉荐书`, the rest moves to body
- `2.周三` (day-only scaffolding) — drop entirely; the extractor already does

If a title is more than ~15 Chinese characters, it's probably a sentence. Shorten it to a real heading and push the explanation into `body`.

## Section names — the four canonical buckets

| In the deck | Aliases the extractor recognises in source |
|---|---|
| 亮点工作 | 亮点工作 |
| 常规工作 | 常规工作 |
| 问题建议 | 问题建议, 工作建议 |
| 值周反思 | 值周反思, 值周思考 |

The skeleton's TOC and divider slides are pre-set to the canonical names. Don't change them.

## Layout selection (already automatic, just so you know)

| Image count | Layout |
|---|---|
| 0 | Either a single body paragraph (if `body` is set) or colored label cards (if `body_blocks` is set). Use `body_blocks` when there are 2–3 distinct points to make. |
| 1 | Centered, ~7 inches wide, ratio preserved. |
| 2 | Side-by-side, equal widths, ratio preserved. |
| 3 | Three columns, equal widths, ratio preserved. |
| 4+ | First three only — the layout doesn't go beyond 3-up. If you have 4 images for one subsection, split into two subsections. |

## Footer

No footer by default. Only add one if the user explicitly asks for it — set `plan["footer"]` to the string you want shown (e.g. `昌平校区 · 第四值周组`).

## Things to actively avoid

- Bullet points with `•` characters in body text — the user dislikes the look. Either use natural prose or split into `body_blocks` cards.
- Adding citation marks `[1]`, `(见图)`, `源：…` in the slide — the user explicitly asked not to add references.
- Decorative full-width colored bars beyond the existing blue header — looks AI-generated.
- Repeating an image across slides. Every image is used exactly once.
