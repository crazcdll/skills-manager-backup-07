"""Parse a 值周汇报 .docx into a plan JSON ready for Claude to review.

Usage:
    python extract_docx.py <input.docx> <out_dir>

Output:
    <out_dir>/plan.json     -- the structured plan (edit titles/subtitles, then pass to build_pptx.py)
    <out_dir>/imgs/imageN.* -- every image extracted from the docx, named the same way it
                                appears in the doc archive (image1.jpeg, image2.png, ...)

The plan groups paragraphs into 4 sections by Chinese heading names. Inside each section,
it splits into "subsections" each time it sees a heading like "1.1 高三化学讲座" or "2.周三".
Images that appear under a subsection are attached to it.

Headings recognised as section starts (any Chinese-punctuation variation accepted):
    亮点工作  常规工作  问题建议 (or 工作建议)  值周反思 (or 值周思考)

Headings recognised as subsection starts: paragraphs whose text starts with a digit + dot
(e.g. "1.", "1.1", "2.周三", "3.2").

You'll usually want to merge or split a few subsections by hand after the extractor runs
— that's expected, not a bug.
"""
from __future__ import annotations
import json
import os
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}
W_T = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'
A_BLIP = '{http://schemas.openxmlformats.org/drawingml/2006/main}blip'
R_EMBED = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed'

# Section keywords -> canonical name we use in the deck
SECTION_KEYS = [
    ('亮点工作', '亮点工作'),
    ('常规工作', '常规工作'),
    ('问题建议', '问题建议'),
    ('工作建议', '问题建议'),  # template's old name maps to new
    ('值周反思', '值周反思'),
    ('值周思考', '值周反思'),
]
SECTION_ORDER = ['亮点工作', '常规工作', '问题建议', '值周反思']

# Subsection heading: starts with digit(s) + "." (and may continue with more numbers/text)
SUBSECTION_RE = re.compile(r'^\s*(\d+(?:\.\d+)*)\s*[.。]?\s*(.*)')
# Strip leading "1.1" / "1." prefix from a title
PREFIX_RE = re.compile(r'^\s*\d+(?:\.\d+)*\s*[.。]?\s*')


def detect_section(text: str) -> str | None:
    t = text.strip()
    for keyword, canonical in SECTION_KEYS:
        if t == keyword or t.endswith(keyword) and len(t) <= len(keyword) + 4:
            return canonical
    return None


def is_day_header(text: str) -> bool:
    """Detect day-only headers like '1.周一', '2.周二' that we want to skip
    (they're scaffolding, not actual subsections)."""
    m = SUBSECTION_RE.match(text)
    if not m:
        return False
    body = m.group(2).strip()
    return bool(re.fullmatch(r'周[一二三四五六日]', body))


def extract(docx_path: str, out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    img_dir = os.path.join(out_dir, 'imgs')
    os.makedirs(img_dir, exist_ok=True)

    with zipfile.ZipFile(docx_path) as z:
        doc_xml = z.read('word/document.xml')
        rels_xml = z.read('word/_rels/document.xml.rels')

        # Build relId -> media path map and copy media out
        rels_root = ET.fromstring(rels_xml)
        rid_to_target = {}
        for r in rels_root:
            rid = r.attrib.get('Id')
            tgt = r.attrib.get('Target')  # e.g. "media/image1.jpeg"
            if tgt and tgt.startswith('media/'):
                rid_to_target[rid] = tgt

        # Copy media files out
        media_basenames = {}
        for rid, tgt in rid_to_target.items():
            arcname = f'word/{tgt}'
            try:
                data = z.read(arcname)
            except KeyError:
                continue
            base = os.path.basename(tgt)
            with open(os.path.join(img_dir, base), 'wb') as f:
                f.write(data)
            media_basenames[rid] = base

    root = ET.fromstring(doc_xml)
    body = root.find('w:body', NS)

    # Walk paragraphs sequentially; group into sections/subsections.
    plan = {
        'cover_title': '__TODO_GENERATE__',
        'cover_team': '__TODO_FILL__',
        'cover_date': '__TODO_FILL__',
        'sections': [{'name': n, 'num': f'{i+1:02d}', 'slides': []}
                     for i, n in enumerate(SECTION_ORDER)],
    }

    current_section = None
    current_slide = None  # dict being built

    def flush():
        nonlocal current_slide
        if current_slide is None:
            return
        # Skip slides with no title and no images
        if not current_slide['title'] and not current_slide['images']:
            current_slide = None
            return
        # Find section by name
        for sec in plan['sections']:
            if sec['name'] == current_section:
                sec['slides'].append(current_slide)
                break
        current_slide = None

    for p in body.findall('w:p', NS):
        text = ''.join(t.text or '' for t in p.iter(W_T)).strip()
        images = []
        for blip in p.iter(A_BLIP):
            embed = blip.attrib.get(R_EMBED)
            if embed and embed in media_basenames:
                images.append(media_basenames[embed])

        # Section header?
        sec = detect_section(text) if text else None
        if sec:
            flush()
            current_section = sec
            continue

        if not current_section:
            # Skip anything before the first section
            continue

        # Day-only scaffolding line — ignore
        if text and is_day_header(text) and not images:
            continue

        # Subsection heading? (Check text regardless of images on the same paragraph —
        # a heading may share a paragraph with its first image.)
        m = SUBSECTION_RE.match(text) if text else None
        if m:
            flush()
            stripped_title = PREFIX_RE.sub('', text).strip()
            current_slide = {
                'title': stripped_title,
                'body': '',
                'body_blocks': [],
                'images': list(images),  # any image on the heading paragraph belongs here
            }
            continue

        # Plain text body line
        if text:
            if current_slide is None:
                current_slide = {'title': text, 'body': '', 'body_blocks': [], 'images': []}
            elif current_slide['body']:
                current_slide['body'] += text
            else:
                current_slide['body'] = text

        # Images on a body/blank paragraph attach to current slide
        if images:
            if current_slide is None:
                current_slide = {'title': '', 'body': '', 'body_blocks': [], 'images': []}
            current_slide['images'].extend(images)

    flush()

    out_json = os.path.join(out_dir, 'plan.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

    # Quick summary to stdout
    n_imgs = sum(len(s['images']) for sec in plan['sections'] for s in sec['slides'])
    print(f'Extracted {n_imgs} images, {sum(len(s["slides"]) for s in plan["sections"])} subsections '
          f'across {len(plan["sections"])} sections')
    print(f'Plan: {out_json}')
    print(f'Images: {img_dir}')
    return plan


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: extract_docx.py <input.docx> <out_dir>', file=sys.stderr)
        sys.exit(2)
    extract(sys.argv[1], sys.argv[2])
