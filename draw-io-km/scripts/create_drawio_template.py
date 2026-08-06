#!/usr/bin/env python3
"""
Create structured .drawio diagram templates from project analysis

This script provides templates for creating different types of diagrams:
- System Architecture
- Workflow/Process Flow
- Component Diagram
- Data Flow Diagram

Usage:
    python3 create_drawio_template.py [OPTIONS] <output_file>

Examples:
    # Create system architecture diagram
    python3 create_drawio_template.py -t architecture my-system.drawio

    # Create workflow diagram
    python3 create_drawio_template.py -t workflow my-workflow.drawio

    # Create with custom title
    python3 create_drawio_template.py my-diagram.drawio -t "My Architecture" --type architecture
"""

import sys
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime


def create_basic_diagram(output_file, title, diagram_type="architecture"):
    """
    Create a basic draw.io diagram structure

    Args:
        output_file: Path to save .drawio file
        title: Diagram title
        diagram_type: Type of diagram (architecture, workflow, component, dataflow)
    """

    # Create basic diagram structure
    root = ET.Element('mxfile', {
        'host': 'app.diagrams.net',
        'modified': datetime.now().isoformat(),
        'agent': 'Mozilla/5.0',
        'etag': 'drawio-template-v2.2',
        'version': '20.0.0'
    })

    diagram = ET.SubElement(root, 'diagram', {
        'id': 'diagram-1',
        'name': 'Page-1'
    })

    mxGraphModel = ET.SubElement(diagram, 'mxGraphModel', {
        'dx': '1200',
        'dy': '800',
        'grid': '1',
        'gridSize': '10',
        'guides': '1',
        'tooltips': '1',
        'connect': '1',
        'arrows': '1',
        'fold': '1',
        'page': '1',
        'pageScale': '1',
        'pageWidth': '827',
        'pageHeight': '1169',
        'background': '#ffffff',
        'math': '0',
        'shadow': '0',
        'defaultFontFamily': 'Noto Sans JP'
    })

    root_cell = ET.SubElement(mxGraphModel, 'root')
    ET.SubElement(root_cell, 'mxCell', {'id': '0'})
    ET.SubElement(root_cell, 'mxCell', {'id': '1', 'parent': '0'})

    # Add title
    title_cell = ET.SubElement(root_cell, 'mxCell', {
        'id': 'title',
        'value': title,
        'style': 'text;html=1;fontSize=28;fontStyle=1;fontFamily=Noto Sans JP;verticalAlign=top;',
        'vertex': '1',
        'parent': '1'
    })
    ET.SubElement(title_cell, 'mxGeometry', {
        'x': '50',
        'y': '20',
        'width': '400',
        'height': '60',
        'as': 'geometry'
    })

    # Add timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ts_cell = ET.SubElement(root_cell, 'mxCell', {
        'id': 'timestamp',
        'value': f'Created: {timestamp}',
        'style': 'text;html=1;fontSize=10;fontFamily=Noto Sans JP;fontColor=#666666;',
        'vertex': '1',
        'parent': '1'
    })
    ET.SubElement(ts_cell, 'mxGeometry', {
        'x': '50',
        'y': '85',
        'width': '200',
        'height': '20',
        'as': 'geometry'
    })

    # Add diagram type specific elements
    if diagram_type == "architecture":
        _add_architecture_elements(root_cell)
    elif diagram_type == "workflow":
        _add_workflow_elements(root_cell)
    elif diagram_type == "component":
        _add_component_elements(root_cell)
    elif diagram_type == "dataflow":
        _add_dataflow_elements(root_cell)

    # Format and write to file
    _indent_xml(root)
    tree = ET.ElementTree(root)
    tree.write(output_file, encoding='utf-8', xml_declaration=True)
    print(f"✓ Created diagram template: {output_file}")
    print(f"  Type: {diagram_type}")
    print(f"  Title: {title}")


def _indent_xml(elem, level=0):
    """Pretty print XML with indentation"""
    indent = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent


def _add_architecture_elements(root_cell):
    """Add architecture diagram elements"""
    # Layer boxes
    layers = [
        {'name': 'Presentation Layer', 'y': 130, 'color': '#e1f5fe'},
        {'name': 'Application Layer', 'y': 230, 'color': '#fff3e0'},
        {'name': 'Data Access Layer', 'y': 330, 'color': '#f3e5f5'},
        {'name': 'Database Layer', 'y': 430, 'color': '#e8f5e9'}
    ]

    for idx, layer in enumerate(layers):
        box = ET.SubElement(root_cell, 'mxCell', {
            'id': f'layer_{idx}',
            'value': layer['name'],
            'style': f'shape=rectangle;rounded=1;fillColor={layer["color"]};strokeColor=#424242;fontSize=14;fontFamily=Noto Sans JP;fontStyle=1;',
            'vertex': '1',
            'parent': '1'
        })
        ET.SubElement(box, 'mxGeometry', {
            'x': '100',
            'y': str(layer['y']),
            'width': '600',
            'height': '60',
            'as': 'geometry'
        })


def _add_workflow_elements(root_cell):
    """Add workflow diagram elements"""
    # Steps
    steps = [
        {'name': 'Start', 'y': 130, 'color': '#c8e6c9'},
        {'name': 'Process 1', 'y': 230, 'color': '#bbdefb'},
        {'name': 'Decision', 'y': 330, 'color': '#ffe0b2'},
        {'name': 'Process 2', 'y': 430, 'color': '#bbdefb'},
        {'name': 'End', 'y': 530, 'color': '#ffcccc'}
    ]

    for idx, step in enumerate(steps):
        box = ET.SubElement(root_cell, 'mxCell', {
            'id': f'step_{idx}',
            'value': step['name'],
            'style': f'shape=rectangle;rounded=1;fillColor={step["color"]};strokeColor=#333333;fontSize=12;fontFamily=Noto Sans JP;',
            'vertex': '1',
            'parent': '1'
        })
        ET.SubElement(box, 'mxGeometry', {
            'x': '200',
            'y': str(step['y']),
            'width': '150',
            'height': '60',
            'as': 'geometry'
        })


def _add_component_elements(root_cell):
    """Add component diagram elements"""
    # Components
    components = [
        {'name': 'Component A', 'y': 130, 'x': 100},
        {'name': 'Component B', 'y': 130, 'x': 350},
        {'name': 'Component C', 'y': 130, 'x': 600},
        {'name': 'Shared Service', 'y': 280, 'x': 350}
    ]

    for idx, comp in enumerate(components):
        box = ET.SubElement(root_cell, 'mxCell', {
            'id': f'component_{idx}',
            'value': comp['name'],
            'style': 'shape=rectangle;rounded=1;fillColor=#c5cae9;strokeColor=#3f51b5;fontSize=12;fontFamily=Noto Sans JP;',
            'vertex': '1',
            'parent': '1'
        })
        ET.SubElement(box, 'mxGeometry', {
            'x': str(comp['x']),
            'y': str(comp['y']),
            'width': '180',
            'height': '80',
            'as': 'geometry'
        })


def _add_dataflow_elements(root_cell):
    """Add data flow diagram elements"""
    # Entities
    entities = [
        {'name': 'Data Source', 'y': 180, 'x': 50, 'shape': 'ellipse'},
        {'name': 'Process', 'y': 180, 'x': 300, 'shape': 'rectangle'},
        {'name': 'Data Store', 'y': 180, 'x': 550},
        {'name': 'Output', 'y': 350, 'x': 300}
    ]

    for idx, entity in enumerate(entities):
        shape_style = 'rounded=1' if entity.get('shape') == 'ellipse' else 'shape=rectangle;rounded=1'
        box = ET.SubElement(root_cell, 'mxCell', {
            'id': f'entity_{idx}',
            'value': entity['name'],
            'style': f'{shape_style};fillColor=#d1c4e9;strokeColor=#512da8;fontSize=12;fontFamily=Noto Sans JP;',
            'vertex': '1',
            'parent': '1'
        })
        ET.SubElement(box, 'mxGeometry', {
            'x': str(entity['x']),
            'y': str(entity['y']),
            'width': '150',
            'height': '60',
            'as': 'geometry'
        })


def main():
    """Command-line interface"""

    parser = argparse.ArgumentParser(
        description='Create structured .drawio diagram templates',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Diagram types:
  architecture  - System architecture with layers
  workflow      - Process workflow with steps
  component     - Component relationships
  dataflow      - Data flow diagram

Examples:
  python3 create_drawio_template.py my-diagram.drawio
  python3 create_drawio_template.py -t architecture my-system.drawio
  python3 create_drawio_template.py --type workflow -t "My Workflow" my-flow.drawio
        '''
    )

    parser.add_argument(
        'output_file',
        help='Output .drawio file path'
    )
    parser.add_argument(
        '-t', '--title',
        help='Diagram title (default: derived from filename)'
    )
    parser.add_argument(
        '--type',
        dest='diagram_type',
        choices=['architecture', 'workflow', 'component', 'dataflow'],
        default='architecture',
        help='Diagram type (default: architecture)'
    )

    args = parser.parse_args()

    # Determine title
    title = args.title
    if not title:
        # Derive from filename
        stem = Path(args.output_file).stem
        title = stem.replace('-', ' ').replace('_', ' ').title()

    try:
        create_basic_diagram(
            output_file=args.output_file,
            title=title,
            diagram_type=args.diagram_type
        )
        print(f"\n✅ Template created successfully: {args.output_file}")
        print(f"\nNext steps:")
        print(f"  1. Open in draw.io: https://draw.io")
        print(f"  2. Import the file and customize")
        print(f"  3. Convert to PNG: drawio -x -f png -s 2 -t -o output.png {args.output_file}")
        print(f"  4. Generate markdown: python3 create_drawio_markdown.py {args.output_file}")
        print(f"  5. Deploy to KM: ./deploy-drawio-to-km.sh {args.output_file}")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

