# Draw.io Skill - KM Document Creation with Embedded Diagrams

## 📋 Summary

Updated the draw.io Skill with direct MCP tool integration for creating KM (Meituan Knowledge Management/学城) documents with embedded `.drawio` XML content. Streamlined workflow with Python and Bash quick references.

## 🎯 What's New

### Main Updates

1. **Updated SKILL.md** (Sections 3.1 & 8)
   - Direct MCP tool: `mcp_tool_km_user_add_collaboration_content_by_sso`
   - Simplified 3-step workflow (Create → Convert → Create KM)
   - XML must be embedded in code block for preservation
   - Python and Bash quick reference workflows

2. **Key Features**
   - ✅ XML embedded in markdown code blocks (```xml ... ```)
   - ✅ Direct MCP tool call (no CLI setup needed)
   - ✅ Multiple document creation methods
   - ✅ Complete troubleshooting guide

## 📦 File Structure

```
.catpaw/skills/draw-io/
├── SKILL.md                          # Main documentation (UPDATED)
├── README.md                          # This file
│
├── scripts/
│   ├── convert-drawio-to-png.sh      # Convert .drawio to PNG
│   ├── find_aws_icon.py              # Find AWS icons
│
└── references/
    ├── layout-guidelines.md          # Layout best practices
    └── aws-icons.md                  # AWS icon reference
```

## 🚀 Quick Start

### 3-Step Workflow

#### Step 1: Create/Edit .drawio File

```bash
# Create in draw.io editor or text editor
# File format: standard XML (.drawio)
```

#### Step 2: Convert to PNG (Optional)

```bash
drawio -x -f png -s 2 -t -o diagram.drawio.png diagram.drawio
```

#### Step 3: Create KM Document with Embedded XML

**Python Method:**

```python
# Read the .drawio file
with open("my-diagram.drawio", "r", encoding="utf-8") as f:
    drawio_xml = f.read()

# Create markdown with XML in code block
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
"""

# Create KM document
result = mcp_tool_km_user_add_collaboration_content_by_sso(
    title="My Diagram Title",
    markdown=markdown,
    parentId=2733918143  # Your parent document ID
)

content_id = result['data']['contentId']
km_url = f"https://km.sankuai.com/collabpage/{content_id}"
print(f"✅ Document created: {km_url}")
```

Done! Your diagram is now on KM with:
- ✅ Embedded .drawio XML in code block
- ✅ Direct importable to draw.io
- ✅ Team-accessible URL

## 📚 Complete Workflow Reference

### Sections in SKILL.md

1. **Section 1-7**: Basic rules, font settings, conversion, best practices
2. **Section 3.1**: ⭐ Create KM Document with Embedded XML (Core workflow)
3. **Section 8**: Complete workflow & quick references (Python & Bash)
4. **Section 9**: Verification checklist
5. **Section 10**: Image display in reveal.js slides

### Key Resources

| Need | Reference |
|------|-----------|
| Quick workflow | SKILL.md Section 8 (Python/Bash examples) |
| Complete reference | SKILL.md full document |
| Troubleshooting | SKILL.md Section 8 (Troubleshooting table) |
| Design guidelines | SKILL.md Sections 5-6 |
| AWS icons | SKILL.md Section 7 |

## 🔧 Scripts Overview

### `convert-drawio-to-png.sh`

**Purpose**: Convert .drawio XML to PNG image

**Usage**:
```bash
bash scripts/convert-drawio-to-png.sh my-diagram.drawio
# or
drawio -x -f png -s 2 -t -o my-diagram.drawio.png my-diagram.drawio
```

**Options**:
- `-s 2`: 2x scale (high resolution)
- `-t`: Transparent background
- `-x`: Export mode

### `find_aws_icon.py`

**Purpose**: Search for AWS icons by keyword

**Usage**:
```bash
python3 scripts/find_aws_icon.py ec2
python3 scripts/find_aws_icon.py lambda
```

## 🎓 How It Works

### Step 1: Create/Edit .drawio
```
Input:  draw.io editor or text editor
Output: my-diagram.drawio (XML file)
```

### Step 2: Convert to PNG (Optional)
```
Input:  my-diagram.drawio
Output: my-diagram.drawio.png (2x scale, transparent background)
Tool:   drawio CLI
Command: drawio -x -f png -s 2 -t -o my-diagram.drawio.png my-diagram.drawio
```

### Step 3: Create KM Document
```
Input:  my-diagram.drawio (XML content)
Output: KM Document URL (https://km.sankuai.com/collabpage/XXXXX)
Tool:   mcp_tool_km_user_add_collaboration_content_by_sso
Method: Embed XML in markdown code block (```xml...```)
```

## 🔄 Update Existing Diagrams

```bash
# 1. Edit in draw.io (local or online)
# 2. Re-export/download the .drawio file
# 3. Re-run step 3 to create new KM document
#    (or update existing with new content_id)
```

## ✨ Key Features

### 1. Simplified Workflow
- **Direct MCP tool**: No CLI setup required
- **3-step process**: Create → Convert (optional) → Create KM document
- **Quick reference**: Python and Bash examples in SKILL.md Section 8

### 2. XML Preservation
- **Code block format**: ```xml...``` ensures no HTML encoding
- **Directly importable**: Copy XML and paste into draw.io
- **Version controllable**: Git-friendly format

### 3. Flexible Document Creation
- **Method 1**: Create with markdown + embedded XML (recommended)
- **Method 2**: Copy from existing document
- **Method 3**: Use template (if available)

### 4. Design Excellence
- Layout guidelines for clarity
- AWS icon integration
- Best practices documentation
- Accessibility guidelines

## 📋 Prerequisites

### Optional: drawio CLI (for PNG conversion)

```bash
# If you want to convert .drawio to PNG
npm install -g drawio
# OR
brew install drawio
```

### For MCP Tool (Required)

The `mcp_tool_km_user_add_collaboration_content_by_sso` is available within CatPaw agent context.
No additional setup is needed if you're using CatPaw.

### For Local Testing

```bash
python3 --version  # Python 3.6+
```

## 🧪 Testing Locally

### Test PNG Conversion

```bash
# 1. Create or edit a .drawio file
# 2. Convert to PNG
drawio -x -f png -s 2 -t -o test-diagram.drawio.png test-diagram.drawio

# 3. Verify PNG created
ls -lh test-diagram.drawio.png
```

### Test KM Document Creation

```bash
# Use CatPaw to call mcp_tool_km_user_add_collaboration_content_by_sso
# (See Quick Start section for Python example)

# Or test with Bash:
python3 << 'EOF'
with open("test-diagram.drawio", "r") as f:
    xml = f.read()

md = f"""# Test Diagram

## Diagram XML Source

```xml
{xml}
```

## Usage
Copy XML above and paste into draw.io
"""

with open("test-diagram.md", "w") as f:
    f.write(md)

print("✅ test-diagram.md created successfully")
EOF
```

## 🎯 Common Use Cases

### Use Case 1: Quick Diagram Documentation
1. Create diagram in draw.io
2. Export as .drawio
3. Use Python code (Quick Start section) to create KM document
4. Share KM URL with team

### Use Case 2: System Architecture Diagram
1. Create architecture diagram
2. Convert to PNG for presentations
3. Create KM document with embedded XML
4. Add to team wiki

### Use Case 3: Process Flow Visualization
1. Create flow diagram
2. Create KM document
3. Use as documentation for processes
4. Keep updated when process changes

## 📖 Documentation Map

| Document | Purpose | Target Audience |
|----------|---------|-----------------|
| `README.md` | Overview & quick start | Everyone (this file) |
| `SKILL.md` Section 3.1 | Create KM Documents | Users creating diagrams |
| `SKILL.md` Section 8 | Quick Python/Bash ref | Developers |
| `SKILL.md` Sections 1-7 | Design guidelines | Diagram designers |
| `SKILL.md` Section 9 | Verification checklist | QA, reviewers |

## 🔍 What Was Updated

### SKILL.md Changes

**Sections Updated**:
- **Section 3.1**: ⭐ NEW - Create Cloud Document with .drawio Content
  - MCP tool introduction
  - XML code block preservation
  - Three document creation methods
  - Quick Python/Bash workflow examples

- **Section 8**: ⭐ ENHANCED - Complete Workflow: Create → Convert → Document → Publish
  - Step-by-step Python reference
  - Step-by-step Bash reference
  - Document creation methods table
  - Document URL format standards
  - Troubleshooting table

- **Sections 1-7, 9-10**: Unchanged (backward compatible)

### Key Improvements

1. **Simplified Process**: 3 main steps instead of complex 4-step workflow
2. **Direct MCP Tool**: No CLI setup required
3. **XML Preservation**: Code block format ensures no HTML encoding
4. **Better Examples**: Python and Bash quick references
5. **Clear Troubleshooting**: Common issues and solutions table

## ✅ Validation Checklist

- [x] SKILL.md updated with MCP tool approach
- [x] Section 3.1 documents XML code block requirement
- [x] Section 8 provides Python/Bash examples
- [x] README updated to reflect new workflow
- [x] Backward compatible (Sections 1-7, 9-10 unchanged)
- [x] Design guidelines still available (Sections 5-6)
- [x] AWS icon guide still available (Section 7)
- [x] Verification checklist still available (Section 9)

## 🚀 Next Steps for Users

1. **Start**: Read Quick Start section above (5 minutes)
2. **Try**: Create a simple .drawio file
3. **Test**: Use Python code to create KM document
4. **Share**: Send KM URL to team
5. **Learn**: Review SKILL.md for design guidelines and best practices

## 🔒 Backward Compatibility

✅ All existing functionality preserved:
- Sections 1-7, 9-10 of SKILL.md unchanged
- Existing scripts still work
- No breaking changes
- Pure additive updates

## 📞 Support & Troubleshooting

### Common Issues

**Problem**: XML not preserved in KM document
**Solution**: Ensure XML is in code block (```xml ... ```) as shown in examples

**Problem**: PNG conversion fails
**Solution**: Install drawio: `brew install drawio` or `npm install -g drawio`

**Problem**: MCP tool not available
**Solution**: Ensure you're using CatPaw agent context

### Documentation

- **Troubleshooting**: See SKILL.md Section 8
- **Design Guidelines**: See SKILL.md Sections 5-6
- **AWS Icons**: See SKILL.md Section 7
- **Verification**: See SKILL.md Section 9 Checklist

---

## Version Information

- **Skill Version**: 2.1 (Updated)
- **Release Date**: 2026-03-03
- **Previous Version**: 2.0 (Script-based approach)
- **Python Version**: 3.6+
- **Main Change**: Direct MCP tool integration for KM document creation

## 🎉 Summary

The draw.io Skill now provides:
- ✅ Simplified 3-step workflow
- ✅ Direct MCP tool integration (no setup needed)
- ✅ XML code block preservation
- ✅ Python and Bash quick references
- ✅ Complete design guidelines
- ✅ Troubleshooting documentation
- ✅ Backward compatible

**Ready to use!** See Quick Start section above.

---

**Last Updated**: 2026-03-03
**Location**: `~/.catpaw/skills/draw-io/README.md`

