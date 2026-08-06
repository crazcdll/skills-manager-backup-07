# CitadelMD In-Place Edit Workflow

Use this reference only when the user explicitly wants to update an existing 学城 document with official CitadelMD syntax, or when a 1.0 document cannot use the CitadelXML update path. For most complex 2.0 edits, prefer the official CitadelXML path because XML nesting is easier to validate.

This workflow uses the official `oa-skills citadel` CLI, not the local `km` command. It overwrites the document body with the edited CitadelMD, so treat it as a safe full-document replace: always read the latest content first, edit the local file minimally, validate conversion, then write it back with `--step-version`.

## Step 1: Resolve Document ID

Extract the numeric `contentId` from:

- `https://km.sankuai.com/collabpage/<contentId>`
- `https://km.sankuai.com/page/<contentId>`

## Step 2: Fetch Latest CitadelMD

```bash
DOC_ID=1234567890
oa-skills citadel getDocumentCitadelMd \
  --contentId "$DOC_ID" \
  --output "/tmp/km-${DOC_ID}.citadelmd"
```

Record the `文档版本（stepVersion）：<number>` printed by the command. This version must be passed to the write step as the concurrency guard.

## Step 3: Edit The Local File Minimally

Edit `/tmp/km-${DOC_ID}.citadelmd` directly.

- Preserve existing `nodeId`, `dataDiffId`, footnote IDs, drawIO/image/file URLs, table macro attributes, and unrelated block ordering.
- Keep custom block nesting balanced: existing custom blocks use `:::tag{attrs} ... :::`.
- Newly inserted nodes may omit `nodeId`.
- If inserting images, attachments, drawIO, audio, or video, upload them to the target document first with the official upload command, then insert the returned CitadelMD snippet.

## Step 4: Validate Conversion

```bash
oa-skills citadel convertMdToJson \
  --file "/tmp/km-${DOC_ID}.citadelmd" \
  --output "/tmp/km-${DOC_ID}.json"
```

## Step 5: Write Back With Step-Version

```bash
oa-skills citadel updateDocumentByMd \
  --contentId "$DOC_ID" \
  --file "/tmp/km-${DOC_ID}.citadelmd" \
  --step-version <stepVersion>
```

If the title changes, update both the `:::title` block inside the CitadelMD file and the metadata title:

```bash
oa-skills citadel updateDocumentByMd \
  --contentId "$DOC_ID" \
  --file "/tmp/km-${DOC_ID}.citadelmd" \
  --step-version <stepVersion> \
  --title "新标题"
```

## Step 6: Return The Document Link

```text
https://km.sankuai.com/collabpage/<contentId>
```

Tell the user to refresh the open 学城 page to see the update.

If `updateDocumentByMd` reports that the step version changed, another editor updated the document after Step 2. Re-fetch with `getDocumentCitadelMd`, re-apply the minimal edit to the new file, re-run conversion validation, then update again.

## Gotchas

- **Do not use read-only Markdown as update input.** `km get`, `getSimpleMarkdown`, summarized content, and copied browser text are for reading only. They can lose `nodeId`, macro attributes, or rich structure and must not be passed to `updateDocumentByMd`.
- **Do not use local `km create --file` syntax as CitadelMD.** Local creation is Markdown-first and treats `:::` CitadelMD macros as plain text. Official CitadelMD update must use `oa-skills citadel getDocumentCitadelMd` and `updateDocumentByMd`.
- **Always use `--step-version`.** Without it, a full-document write can overwrite edits made by another user after you fetched the file.
- **Never rewrite the whole document for a small edit.** Keep edits narrowly scoped and preserve unrelated formatting, ordering, IDs, URLs, and macro attributes.
- **Do not paste external resource URLs directly.** Images, attachments, drawIO, audio, and video must be uploaded to the target document first so their permissions are bound to that document.
- **Title changes need two updates.** Change the `:::title` block in CitadelMD and pass `--title`; doing only one side leaves title metadata inconsistent.
- **Prefer XML unless CitadelMD is required.** For 2.0 docs, official CitadelXML is usually easier to validate. Use CitadelMD when explicitly requested or when XML cannot handle the document.
