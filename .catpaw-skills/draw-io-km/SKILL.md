---
name: draw-io-km
description: draw.io diagram creation, editing, and review. Use for .drawio XML editing, PNG conversion, layout adjustment, and upload the a new drawio doc to km.sankuai.com（学城）.

metadata:
  skillhub.creator: "heyuzhi02"
  skillhub.updater: "heyuzhi02"
  skillhub.version: "V1"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "1663"
---

# draw.io Diagram Skill

## 1. Basic Rules

- Edit only `.drawio` files
- Do not directly edit `.drawio.png` files
- Use auto-generated `.drawio.png` by pre-commit hook in slides
- check the mcp configs and you can find the usages here:https://km.sankuai.com/collabpage/2748718351

```
   {
  "mcpServers": {
    
    "km_user": {
      "url": "http://mcphub-server.sankuai.com/mcphub-b/f0b6769b8bb044"
    }
  }}


```
## 2. Font Settings

For diagrams used in Quarto slides,
specify `defaultFontFamily` in mxGraphModel tag:

```xml
<mxGraphModel defaultFontFamily="Noto Sans JP" dx="1200" dy="800" grid="1" />
```

Also explicitly specify `fontFamily` in each text element's style attribute:

```xml
<mxCell style="text;html=1;fontSize=27;fontFamily=Noto Sans JP;" />
```

## 3. Conversion Commands

See conversion script at [scripts/convert-drawio-to-png.sh](scripts/convert-drawio-to-png.sh).

```sh
# Convert all .drawio files
mise exec -- pre-commit run --all-files

# Convert specific .drawio file
mise exec -- pre-commit run convert-drawio-to-png --files assets/my-diagram.drawio

# Run script directly (using skill's script)
bash ~/.claude/skills/draw-io/scripts/convert-drawio-to-png.sh assets/diagram1.drawio
```

Internal command used:

```sh
drawio -x -f png -s 2 -t -o output.drawio.png input.drawio
```

| Option | Description |
|--------|-------------|
| `-x` | Export mode |
| `-f png` | PNG format output |
| `-s 2` | 2x scale (high resolution) |
| `-t` | Transparent background |
| `-o` | Output file path |

## 3.1. Create Cloud Document with .drawio Content

After generating `.drawio` files, create a cloud document (Meituan Knowledge Management/学城) and embed the `.drawio` content.

### ✅ CRITICAL: XML Must Be Embedded in Code Block

The `.drawio` XML **must be embedded in a code block** (```xml ... ```) to ensure:
- XML is preserved exactly as-is without HTML entity encoding
- Can be copied and imported directly into draw.io
- Remains editable and version-controllable

### Quick Start: Create KM Document with Markdown + XML

Use the `mcp_tool_km_user_add_collaboration_content_by_sso` MCP tool to create documents with embedded XML:

```python
# Method 1: Create with Markdown content (most common)
mcp_tool_km_user_add_collaboration_content_by_sso(
    title="Your Diagram Title",
    markdown="""# Your Diagram Title

## Diagram XML Source

```xml
<mxfile>
  <!-- Your .drawio XML content here -->
</mxfile>
```

## Usage

1. Copy the XML from the code block above
2. Go to [draw.io](https://draw.io)
3. File → Open → Paste the XML
4. Edit and export to PNG
5. Update this document with new XML to save changes
""",
    parentId=2733918143  # Replace with your parent document ID
)

# Method 2: Create by copying from existing document
mcp_tool_km_user_add_collaboration_content_by_sso(
    title="New Diagram Copy",
    copyFromContentId="2748758260",  # Copy from existing diagram
    parentId=2733918143
)

# Method 3: Create from template
mcp_tool_km_user_add_collaboration_content_by_sso(
    title="Diagram from Template",
    templateId="template_id",  # Use template to create
    parentId=2733918143
)
```

### Document Creation Methods

| Method | Parameter | Use Case |
|--------|-----------|----------|
| **Markdown** | `markdown` | Create document with custom markdown + XML code block |
| **Copy** | `copyFromContentId` | Duplicate an existing diagram document |
| **Template** | `templateId` | Create from predefined template |

### Python Workflow Example

```python
import os

# Step 1: Read your .drawio file
with open("my-diagram.drawio", "r", encoding="utf-8") as f:
    drawio_xml = f.read()

# Step 2: Create markdown with XML in code block
markdown = f"""# My Diagram Title

## Diagram XML Source

```xml
{drawio_xml}
```

## Usage

1. Copy the XML from the code block above
2. Go to [draw.io](https://draw.io)
3. File → Open → Paste the XML
4. Edit and export to PNG

## Key Features

- Embedded diagram source
- Version controllable
- Directly importable to draw.io
"""

# Step 3: Call MCP tool to create KM document
# (This would be called within your agent/skill context)
mcp_tool_km_user_add_collaboration_content_by_sso(
    title="My Diagram Title",
    markdown=markdown,
    parentId=2733918143  # Your parent document ID
)

# Response: {"status": {"code": 0, "msg": "成功"}, "data": {"success": true, "contentId": XXXXX}}
```

### Verification Checklist

After creating KM document:

- [ ] ```xml code block opening tag present
- [ ] ``` code block closing tag present
- [ ] `<mxfile` root element exists (not HTML-encoded)
- [ ] `<mxGraphModel` element exists
- [ ] All `mxCell` elements preserved
- [ ] No excessive HTML entity encoding detected
- [ ] Can copy raw XML from code block and import into draw.io directly

## 4. Layout Adjustment

### 4.1. Coordinate Adjustment Steps

1. Open `.drawio` file in text editor (plain XML format)
2. Find `mxCell` for element to adjust (search by `value` attribute for text)
3. Adjust coordinates in `mxGeometry` tag
   - `x`: Position from left
   - `y`: Position from top
   - `width`: Width
   - `height`: Height
4. Run conversion and verify

### 4.2. Coordinate Calculation

- Element center coordinate = `y + (height / 2)`
- To align multiple elements, calculate and match center coordinates

## 5. Design Principles

### 5.1. Basic Principles

- Clarity: Create simple, visually clean diagrams
- Consistency: Unify colors, fonts, icon sizes, line thickness
- Accuracy: Do not sacrifice accuracy for simplification

### 5.2. Element Rules

- Label all elements
- Use arrows to indicate direction
  (prefer 2 unidirectional arrows over bidirectional)
- Use latest official icons
- Add legend to explain custom symbols

### 5.3. Accessibility

- Ensure sufficient color contrast
- Use patterns in addition to colors

### 5.4. Progressive Disclosure

Separate complex systems into staged diagrams:

| Diagram Type | Purpose |
|--------------|---------|
| Context Diagram | System overview from external perspective |
| System Diagram | Main components and relationships |
| Component Diagram | Technical details and integration points |
| Deployment Diagram | Infrastructure configuration |
| Data Flow Diagram | Data flow and transformation |
| Sequence Diagram | Time-series interactions |

### 5.5. Metadata

Include title, description, last updated, author, and version in diagrams.

## 6. Best Practices

### 6.1. Background Color

- Remove `background="#ffffff"`
- Transparent background adapts to various themes

### 6.2. Font Size

- Use 1.5x standard font size (around 18px) for PDF readability

### 6.3. Japanese Text Width

- Allow 30-40px per character
- Insufficient width causes unintended line breaks

```xml
<!-- For 10-character text, allow 300-400px -->
<mxGeometry x="140" y="60" width="400" height="40" />
```

### 6.4. Arrow Placement

- Always place arrows at back (position in XML right after Title)
- Position arrows to avoid overlapping with labels
- Keep arrow start/end at least 20px from label bottom edge

```xml
<root>
  <!-- Title -->
  <mxCell id="title" value="Title" vertex="1" parent="1"/>

  <!-- Arrows (back layer) -->
  <mxCell id="arrow1" style="edgeStyle=orthogonalEdgeStyle;" edge="1" parent="1"/>

  <!-- Other elements (front layer) -->
  <mxCell id="box1" vertex="1" parent="1"/>
</root>
```

### 6.5. Arrow Connection to Text Labels

For text elements, exitX/exitY don't work, so use explicit coordinates:

```xml
<!-- Good: Explicit coordinates with sourcePoint/targetPoint -->
<mxCell id="arrow" style="..." edge="1" parent="1">
  <mxGeometry relative="1" as="geometry">
    <mxPoint x="1279" y="500" as="sourcePoint"/>
    <mxPoint x="119" y="500" as="targetPoint"/>
    <Array as="points">
      <mxPoint x="1279" y="560"/>
      <mxPoint x="119" y="560"/>
    </Array>
  </mxGeometry>
</mxCell>
```

### 6.6. edgeLabel Offset Adjustment

Adjust offset attribute to distance arrow labels from arrows:

```xml
<root>
  <!-- Place above arrow (negative value to distance) -->
  <!-- <mxPoint x="0" y="-40" as="offset"/> -->

  <!-- Place below arrow (positive value to distance) -->
  <!-- <mxPoint x="0" y="40" as="offset"/> -->
</root>
```

### 6.7. Remove Unnecessary Elements

- Remove decorative icons irrelevant to context
- Example: If ECR exists, separate Docker icon is unnecessary

### 6.8. Labels and Headings

- Service name only: 1 line
- Service name + supplementary info: 2 lines with line break
- Redundant notation (e.g., ECR Container Registry): shorten to 1 line
- Use `&lt;br&gt;` tag for line breaks

### 6.9. Background Frame and Internal Element Placement

When placing elements inside background frames (grouping boxes),
ensure sufficient margin.

- YOU MUST: Internal elements must have at least 30px margin from frame boundary
- YOU MUST: Account for rounded corners (`rounded=1`) and stroke width
- YOU MUST: Always visually verify PNG output for overflow

Coordinate calculation verification:

```text
Background frame: y=20, height=400 -> range is y=20-420
Internal element top: frame y + 30 or more (e.g., y=50)
Internal element bottom: frame y + height - 30 or less (e.g., up to y=390)
```

Bad example (may overflow):

```xml
<root>
  <!-- Background frame -->
  <mxCell id="bg" style="rounded=1;strokeWidth=3;fillColor=#ffffff">
    <mxGeometry x="500" y="20" width="560" height="400" />
  </mxCell>
  <!-- Text: y=30 is too close to frame top (y=20) -->
  <mxCell id="label" value="Title" style="text;fontSize=14;">
    <mxGeometry x="510" y="30" width="540" height="35" />
  </mxCell>
</root>
```

Good example (sufficient margin):

```xml
<root>
  <!-- Background frame -->
  <mxCell id="bg" style="rounded=1;strokeWidth=3;fillColor=#ffffff">
    <mxGeometry x="500" y="20" width="560" height="430" />
  </mxCell>
  <!-- Text: y=50 is 30px from frame top (y=20) -->
  <mxCell id="label" value="Title" style="text;fontSize=14;">
    <mxGeometry x="510" y="50" width="540" height="35" />
  </mxCell>
</root>
```

## 7. Reference

- [Layout Guidelines](references/layout-guidelines.md)
- [AWS Icons](references/aws-icons.md)
- [AWS Icon Search Script](scripts/find_aws_icon.py)
- KM Document Tools Skill - For cloud document operations (see /claude/skills/km-doc-tools/SKILL.md)

AWS icon search examples:

```sh
python ~/.claude/skills/draw-io/scripts/find_aws_icon.py ec2
python ~/.claude/skills/draw-io/scripts/find_aws_icon.py lambda
```

## 7.1. XML Validation and Auto-Repair Before KM Upload

### ⚠️ CRITICAL: Validate .drawio Files Before Uploading

Before uploading any `.drawio` file to KM, **always validate and repair** the XML structure to prevent parsing errors.

### Validation Steps

#### Step 1: Validate XML Structure

```bash
# Validate the .drawio file
xmllint --noout diagram.drawio
```

If validation passes, you'll see no output. If there are errors, you'll see messages like:
```
diagram.drawio:15: parser error : xmlParseEntityRef: no name
```

#### Step 2: Common XML Issues and Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| `xmlParseEntityRef: no name` | Unescaped `&` in text/attributes | Replace `&` with `&amp;` |
| Missing closing tags | Incomplete XML structure | Ensure all tags properly nested/closed |
| `<` or `>` in text | Unescaped angle brackets | Replace `<` with `&lt;` and `>` with `&gt;` |

### XML Special Characters Escape Rules

Always escape these characters in XML:

| Character | Escape Sequence |
|-----------|-----------------|
| `&` | `&amp;` |
| `<` | `&lt;` |
| `>` | `&gt;` |
| `"` | `&quot;` |
| `'` | `&apos;` |

### Auto-Repair Python Script

Use this Python script to automatically detect and fix common XML issues:

```python
import re
import sys
from pathlib import Path

def repair_drawio_xml(filepath):
    """
    Automatically repair common XML issues in .drawio files.

    Fixes:
    - Unescaped & characters (& → &amp;)
    - Unescaped < and > in text values
    - Missing closing tags
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Fix: Unescaped & characters (but not already escaped &amp;, &lt;, &gt;, &quot;, &apos;)
    # Use negative lookbehind to avoid double-escaping
    content = re.sub(r'&(?!(?:amp|lt|gt|quot|apos);)', '&amp;', content)

    # Verify XML structure by checking for proper closing tags
    # Count opening and closing tags
    open_mxfile = content.count('<mxfile')
    close_mxfile = content.count('</mxfile>')
    open_diagram = content.count('<diagram')
    close_diagram = content.count('</diagram>')
    open_graph = content.count('<mxGraphModel')
    close_graph = content.count('</mxGraphModel>')

    issues = []
    if open_mxfile != close_mxfile:
        issues.append(f"⚠️  Mismatched <mxfile> tags: {open_mxfile} open, {close_mxfile} close")
    if open_diagram != close_diagram:
        issues.append(f"⚠️  Mismatched <diagram> tags: {open_diagram} open, {close_diagram} close")
    if open_graph != close_graph:
        issues.append(f"⚠️  Mismatched <mxGraphModel> tags: {open_graph} open, {close_graph} close")

    # Write repaired content if changed
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Repaired {filepath}")
        print(f"   - Fixed unescaped & characters")
        return True, issues
    else:
        print(f"✅ {filepath} has no automatic fixes needed")
        return False, issues

def validate_and_fix(filepath):
    """Main validation and repair workflow."""
    print(f"\n📋 Validating {filepath}...")

    # Step 1: Auto-repair common issues
    repaired, issues = repair_drawio_xml(filepath)

    # Step 2: Run xmllint validation
    import subprocess
    result = subprocess.run(['xmllint', '--noout', filepath],
                          capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅ XML validation passed!")
        if issues:
            print(f"\n⚠️  Warnings (not critical):")
            for issue in issues:
                print(f"   {issue}")
        return True
    else:
        print(f"❌ XML validation failed:")
        print(result.stderr)
        print(f"\n💡 Try these fixes:")
        print(f"   1. Ensure all & are escaped as &amp;")
        print(f"   2. Check for unclosed tags")
        print(f"   3. Verify proper XML nesting")
        return False

# Usage
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python repair_drawio.py <file.drawio>")
        sys.exit(1)

    filepath = sys.argv[1]
    success = validate_and_fix(filepath)
    sys.exit(0 if success else 1)
```

### Usage Workflow

```bash
# 1. Repair and validate your .drawio file
python repair_drawio.py diagram.drawio

# 2. If validation passes, proceed to create KM document
# (see Section 7.2 below)

# 3. Manual validation if needed
xmllint --noout diagram.drawio
```

### Pre-Upload Checklist

Before uploading to KM, verify:

- [ ] `xmllint --noout diagram.drawio` returns no errors
- [ ] All `&` symbols are escaped as `&amp;`
- [ ] Opening and closing tags match (e.g., `<mxfile>...` has `</mxfile>`)
- [ ] All attributes in quotes are properly closed
- [ ] No syntax errors in XML

## 7.2. Integration with KM (Meituan Knowledge Management)

For creating and managing cloud documents with `.drawio` content, use the MCP tool `mcp_tool_km_user_add_collaboration_content_by_sso`:

- **Method**: Direct MCP tool call (no CLI setup required)
- **Create Document**: `mcp_tool_km_user_add_collaboration_content_by_sso(title="...", markdown="...", parentId=XXXXX)`
- **Full KM Documentation**: See [KM Document Tools SKILL](https://km.sankuai.com/collabpage/2708424384)

## 7.3. Pre-Upload XML Validation Workflow (CRITICAL)

**⚠️ MANDATORY**: Before uploading any `.drawio` file to KM, you MUST:
1. Validate XML structure using `xmllint`
2. Auto-repair common issues if needed
3. Verify validation passes
4. Only then proceed to KM upload

### Complete Validation & Repair Process

```bash
# Step 1: Validate the .drawio file XML structure
xmllint --noout your-diagram.drawio

# If validation FAILS, proceed to Step 2:
# If validation PASSES, skip to Step 3
```

**If validation fails**, run the auto-repair script:

```bash
python3 << 'PYTHON_EOF'
import re
import subprocess
from pathlib import Path

def repair_and_validate_drawio(filepath):
    """Complete validation and repair workflow."""
    print(f"\n🔧 Starting validation and repair for: {filepath}")

    # Read file
    with open(filepath, 'r', encoding='utf-8') as f:
        original = f.read()

    content = original

    # Auto-repair: Fix unescaped & (but not already escaped entities)
    content = re.sub(r'&(?!(?:amp|lt|gt|quot|apos);)', '&amp;', content)

    # Write back if changed
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Auto-repaired file (fixed unescaped & characters)")
    else:
        print(f"ℹ️  No auto-repairs needed")

    # Validate with xmllint
    print(f"\n📋 Running xmllint validation...")
    result = subprocess.run(['xmllint', '--noout', filepath],
                          capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅ XML validation PASSED!")
        print(f"\n✨ This file is safe to upload to KM")
        return True
    else:
        print(f"❌ XML validation FAILED:")
        print(result.stderr)
        print(f"\n💡 Manual fixes needed:")
        print(f"   1. Check for unescaped & (should be &amp;)")
        print(f"   2. Verify all < and > in text are escaped (&lt; &gt;)")
        print(f"   3. Ensure all XML tags are properly closed")
        return False

# Usage
if __name__ == "__main__":
    import sys
    filepath = sys.argv[1] if len(sys.argv) > 1 else "diagram.drawio"
    success = repair_and_validate_drawio(filepath)
    sys.exit(0 if success else 1)
PYTHON_EOF

# Pass your diagram file as argument:
# python3 repair_script.py your-diagram.drawio
```

### Validation Checklist Before KM Upload

```bash
# Run this BEFORE uploading to KM:
xmllint --noout diagram.drawio && echo "✅ Ready for KM upload!" || echo "❌ Fix errors first!"
```

**Expected outputs**:
- ✅ **No output + exit code 0**: File is valid, proceed with KM upload
- ❌ **Error messages + exit code 1**: File has errors, run auto-repair script above

### Common Validation Errors & Quick Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `xmlParseEntityRef: no name` | Unescaped `&` in text/attributes | Replace `&` → `&amp;` |
| `Start tag requires '>'` | Missing closing `>` on tag | Verify tag syntax: `<mxCell ... />` |
| `EntityRef: expecting ';'` | Incomplete entity reference | Check for malformed `&` sequences |
| `Unexpected end of file` | Unclosed tags | Verify `</mxfile>` closing tag exists |

### Example Safe Workflow

```bash
#!/bin/bash
# Safe workflow for diagram upload

DIAGRAM="my-diagram.drawio"

echo "1️⃣  Validating XML..."
if xmllint --noout "$DIAGRAM"; then
    echo "✅ XML is valid!"

    echo -e "\n2️⃣  File is safe to upload to KM"
    echo "   → Proceed with mcp_tool_km_user_add_collaboration_content_by_sso"
else
    echo "❌ XML has errors. Running auto-repair..."
    # Run auto-repair script here
    echo "   → Re-run validation after repair"
    exit 1
fi
```

## 8. Complete Workflow: Create → Validate → Convert → Document → Publish

Quick reference for creating and publishing diagrams:

1. **Create/Edit .drawio** in text editor or draw.io desktop
2. **Validate .drawio XML**: Run `xmllint --noout diagram.drawio` (see Section 7.3)
3. **Auto-repair if needed**: Use repair script above if validation fails
4. **Re-validate**: Confirm `xmllint --noout diagram.drawio` passes
5. **Convert to PNG**: `drawio -x -f png -s 2 -t -o diagram.drawio.png diagram.drawio`
6. **Generate Markdown** with XML in code block (see Section 3.1)
7. **Publish to KM**: Use `mcp_tool_km_user_add_collaboration_content_by_sso` MCP tool (see Section 7.2)

### Quick Python Workflow Reference

```python
# 1. Read your .drawio file
with open("my-diagram.drawio", "r", encoding="utf-8") as f:
    drawio_xml = f.read()

# 2. Create markdown with XML in code block
markdown = f"""# My Diagram Title

## Diagram XML Source

```xml
{drawio_xml}
```

## Usage

1. Copy the XML from the code block above
2. Go to [draw.io](https://draw.io)
3. File → Open → Paste the XML
4. Edit and export to PNG
5. Update this document with new XML to save changes
"""

# 3. Create KM document using MCP tool
result = mcp_tool_km_user_add_collaboration_content_by_sso(
    title="My Diagram Title",
    markdown=markdown,
    parentId=2733918143  # Your parent document ID
)

# Response: {"status": {"code": 0, "msg": "成功"}, "data": {"success": true, "contentId": XXXXX}}
content_id = result['data']['contentId']
km_url = f"https://km.sankuai.com/collabpage/{content_id}"
print(f"✅ Document created: {km_url}")
```

### Quick Bash + drawio Command Reference

```bash
# 1. Convert diagram to PNG
drawio -x -f png -s 2 -t -o diagram.drawio.png diagram.drawio

# 2. Create Markdown with XML in code block
python3 << 'PYTHON_EOF'
with open("diagram.drawio", "r") as f:
    xml = f.read()

md = f"""# My Diagram

## Diagram XML

```xml
{xml}
```

## Usage

Copy XML above and paste into draw.io (File → Open)
"""

with open("diagram.md", "w") as f:
    f.write(md)
PYTHON_EOF

# 3. Use MCP tool to create KM document
# (Call within your agent/skill context with mcp_tool_km_user_add_collaboration_content_by_sso)
```

### Document Creation Methods

Choose the appropriate method based on your use case:

| Scenario | Method | Example |
|----------|--------|---------|
| Create new diagram document | `markdown` parameter | Pass markdown with embedded XML code block |
| Copy existing diagram | `copyFromContentId` parameter | `copyFromContentId="2748758260"` |
| Use predefined template | `templateId` parameter | `templateId="diagram_template_v1"` |

**All methods require:**
- `title`: Document title (string)
- `parentId`: Parent document ID (integer) - document will be created under this parent

### Document URL Format

After creating a KM document, always return the document ID with the complete URL link:

**Format**: `https://km.sankuai.com/collabpage/{contentId}`

**Example Output**:
```
✅ Document created: https://km.sankuai.com/collabpage/2748968100
```

**Python Example**:
```python
result = mcp_tool_km_user_add_collaboration_content_by_sso(
    title="My Diagram",
    markdown=markdown,
    parentId=2733918143
)

content_id = result['data']['contentId']
km_url = f"https://km.sankuai.com/collabpage/{content_id}"
print(f"✅ Document created: {km_url}")
# Output: ✅ Document created: https://km.sankuai.com/collabpage/2748968100
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| `drawio: command not found` | `brew install drawio` or `npm install -g drawio` |
| PNG not generated | Check XML validity: `xmllint --noout diagram.drawio` |
| MCP tool error | Ensure you're calling the tool within proper agent/skill context |
| XML not preserved in KM | Verify markdown has XML in code block (```xml ... ```) |
| Document not visible | Check `parentId` is correct and you have access to parent document |

## 9. Pre-Upload Validation Checklist

**⚠️ MANDATORY BEFORE KM UPLOAD**:

### XML Validation Steps

- [ ] Run `xmllint --noout diagram.drawio` - must return no errors
- [ ] If errors found, run auto-repair script from Section 7.3
- [ ] Re-run `xmllint --noout diagram.drawio` - verify passes
- [ ] All `&` symbols are escaped as `&amp;`
- [ ] All `<` and `>` in text are escaped as `&lt;` and `&gt;`
- [ ] All XML tags are properly closed
- [ ] Confirmed: `</mxfile>` closing tag exists at end
- [ ] No `xmlParseEntityRef` or `EntityRef` errors

### Diagram Quality Checklist

- [ ] No background color set (page="0")
- [ ] Font size appropriate (larger recommended)
- [ ] Arrows placed at back layer
- [ ] Arrows not overlapping labels (verify in PNG)
- [ ] Arrow start/end sufficiently distant from labels (at least 20px)
- [ ] Arrows not penetrating boxes or icons (verify in PNG)
- [ ] Internal elements not overflowing background frame (verify in PNG)
- [ ] 30px+ margin between background frame and internal elements
- [ ] AWS service names are official names/correct abbreviations
- [ ] AWS icons are latest version (mxgraph.aws4.*)
- [ ] No unnecessary elements remaining
- [ ] Visually verified PNG conversion

### KM Publishing Checklist

- [ ] XML validation passed (see XML Validation Steps above)
- [ ] PNG conversion successful
- [ ] Cloud document created with .drawio content
- [ ] Document shared with relevant team members
- [ ] Version number and date documented
- [ ] Document ID returned with complete KM URL link (`https://km.sankuai.com/collabpage/{contentId}`)

## 10. Image Display in reveal.js Slides

Add `auto-stretch: false` to YAML header:

```yaml
---
title: "Your Presentation"
format:
  revealjs:
    auto-stretch: false
---
```

This ensures correct image display on mobile devices.
