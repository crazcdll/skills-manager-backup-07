#!/usr/bin/env python3
"""
Reusable script: Generate Markdown documentation with embedded .drawio XML

This script creates a comprehensive Markdown document from a .drawio file,
including the diagram XML, PNG reference, usage instructions, and metadata.

Usage:
    python3 create_drawio_markdown.py <drawio_file> [output_md] [title]

Examples:
    python3 create_drawio_markdown.py my-diagram.drawio
    python3 create_drawio_markdown.py my-diagram.drawio my-doc.md "System Architecture"
    python3 create_drawio_markdown.py --help
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime


def create_drawio_markdown_doc(
    drawio_file,
    output_md_file=None,
    title=None,
    overview="",
    usage_notes="",
    metadata=None,
):
    """
    Create Markdown document with embedded .drawio XML content

    IMPORTANT: XML is embedded as RAW CONTENT (not code block) to ensure:
    - ✅ XML is preserved exactly as-is when inserted into KM documents
    - ✅ Can be copied and directly imported into draw.io
    - ✅ Remains editable and version-controllable

    DO NOT wrap XML in code blocks (```xml ... ```) as they may be treated
    as display-only and not preserved during KM document rendering.

    Args:
        drawio_file: Path to .drawio file
        output_md_file: Path to save generated .md file (default: replace .drawio with .md)
        title: Document title (default: derived from filename)
        overview: Brief description of the diagram
        usage_notes: Custom usage instructions
        metadata: Dict with additional metadata (author, version, created_date)

    Returns:
        Path to generated markdown file

    Raises:
        FileNotFoundError: If drawio_file doesn't exist
        IOError: If unable to write output file
    """

    # Read drawio file
    drawio_path = Path(drawio_file)
    if not drawio_path.exists():
        raise FileNotFoundError(f"Diagram file not found: {drawio_file}")

    with open(drawio_path, "r", encoding="utf-8") as f:
        drawio_xml = f.read()

    # Set default output file
    if output_md_file is None:
        output_md_file = drawio_path.with_suffix(".md")

    # Set default title
    if title is None:
        title = drawio_path.stem.replace("-", " ").replace("_", " ").title()

    # Prepare metadata
    if metadata is None:
        metadata = {}

    created_date = metadata.get("created_date", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    version = metadata.get("version", "1.0")
    author = metadata.get("author", "Auto-generated")

    # Determine PNG file reference path (handle cross-directory cases)
    png_abs_path = drawio_path.with_suffix(".drawio.png")
    output_path_obj = Path(output_md_file) if output_md_file else drawio_path.with_suffix(".md")

    # Calculate relative path from markdown to PNG
    try:
        # If output markdown is in same directory as drawio, use just filename
        if output_path_obj.parent == drawio_path.parent:
            png_file = png_abs_path.name
        else:
            # Different directories, use relative path
            png_file = os.path.relpath(png_abs_path, output_path_obj.parent)
    except ValueError:
        # Different drives on Windows, fallback to filename
        png_file = png_abs_path.name

    # Create default usage notes if not provided
    if not usage_notes:
        usage_notes = f"""
### How to Edit

1. Download the diagram XML from the "Diagram XML Source" section below
2. Open in [draw.io](https://draw.io):
   - Go to File → Open → and select the XML file
   - Or drag & drop the XML into draw.io editor
3. Make your edits
4. Export to PNG:
   ```bash
   drawio -x -f png -s 2 -t -o {drawio_path.stem}.drawio.png {drawio_path.name}
   ```
5. Update this document with the new PNG and XML

### How to View

- View the PNG image embedded in the "Diagram Visualization" section
- Open the XML in draw.io for interactive editing
- Share the KM document URL with team members

### How to Export

```bash
# Export as PNG (recommended for presentations)
drawio -x -f png -s 2 -t -o diagram.png diagram.drawio

# Export as PDF
drawio -x -f pdf -o diagram.pdf diagram.drawio

# Export as SVG (for web use)
drawio -x -f svg -o diagram.svg diagram.drawio
```

### Version Control

- Keep both PNG and XML files in sync
- Update the XML source when making diagram changes
- Re-generate PNG after XML modifications using the export commands above
- Commit both files to version control for team collaboration
"""

    # Create markdown content
    markdown_content = f"""# {title} - v{version}

**Created**: {created_date}
**Author**: {author}
**Source File**: `{drawio_path.name}`

## Overview

{overview if overview else 'Diagram visualization of system architecture, workflow, or process flow.'}

## Diagram Visualization

The diagram below provides a visual representation of the system structure:

![{title}]({png_file})

## Diagram Details

This diagram was created using [draw.io](https://draw.io) and contains the following:

- System components and services
- Relationships and interactions between components
- Data flow and integration points
- Process workflows and sequences

## Usage Instructions
{usage_notes}

## Diagram XML Source

The complete diagram XML is embedded below for version control, re-importing to draw.io, and documentation:

```xml
{drawio_xml}
```

## Notes

- **PNG and XML Sync**: Keep both the PNG and XML files in sync for consistency
- **Editing**: Always edit the `.drawio` XML file, then re-generate PNG
- **Sharing**: Share the KM document URL with team members for collaboration
- **Updates**: After making changes, update both the PNG and this markdown document

## File Locations

| File | Purpose |
|------|---------|
| `{drawio_path.name}` | Diagram XML source (editable in draw.io) |
| `{png_file}` | Exported PNG image (for viewing/presentations) |
| `{Path(output_md_file).name}` | This markdown documentation |
| KM Document | Published documentation link (created via `km create`) |

## Related Resources

- **draw.io Website**: https://draw.io
- **KM Document Tools**: See `.catpaw/skills/draw-io/SKILL.md`
- **Diagram Conversion**: See `.catpaw/skills/draw-io/scripts/convert-drawio-to-png.sh`

---

*Generated by draw.io Skill v2.2 (2026-03-02)*
*For documentation updates, see SKILL.md section 11: Complete 4-Step Workflow*
"""

    # Write markdown file
    output_path = Path(output_md_file)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    print(f"✓ Markdown document created: {output_path}")
    print(f"  Size: {output_path.stat().st_size:,} bytes")
    print(f"  Title: {title}")
    print(f"  PNG Reference: {png_file}")

    return str(output_path)


def main():
    """Command-line interface for the script"""

    parser = argparse.ArgumentParser(
        description="Generate Markdown documentation from .drawio files with embedded XML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate with defaults (output to <filename>.md)
  python3 create_drawio_markdown.py my-diagram.drawio

  # Specify output filename and title
  python3 create_drawio_markdown.py my-diagram.drawio my-doc.md "System Architecture"

  # With custom metadata
  python3 create_drawio_markdown.py system.drawio -o system.md -t "System Design" -a "John Doe" -v "2.0"

  # Create in specific directory
  python3 create_drawio_markdown.py /path/to/diagram.drawio -o ./docs/diagram.md
        """,
    )

    parser.add_argument("drawio_file", help="Path to .drawio file")
    parser.add_argument(
        "-o",
        "--output",
        dest="output_md_file",
        help="Output markdown file path (default: <input>.md)",
    )
    parser.add_argument("-t", "--title", help="Document title (default: derived from filename)")
    parser.add_argument(
        "-a", "--author", help="Author name (default: Auto-generated)", dest="author"
    )
    parser.add_argument(
        "-v", "--version", help="Version number (default: 1.0)", dest="version"
    )
    parser.add_argument(
        "-d", "--description", help="Overview/description of the diagram", dest="overview"
    )

    args = parser.parse_args()

    try:
        # Prepare metadata
        metadata = {}
        if args.author:
            metadata["author"] = args.author
        if args.version:
            metadata["version"] = args.version

        # Create markdown
        output_file = create_drawio_markdown_doc(
            drawio_file=args.drawio_file,
            output_md_file=args.output_md_file,
            title=args.title,
            overview=args.overview or "",
            metadata=metadata,
        )

        print(f"\n✅ Successfully generated: {output_file}")
        return 0

    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

