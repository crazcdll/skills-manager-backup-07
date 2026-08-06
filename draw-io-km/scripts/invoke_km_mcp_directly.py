#!/usr/bin/env python3
"""
🎯 MCP Tool Direct Invoker - Execute within Claude's MCP Context

This script MUST be run from within Claude's MCP context to work properly.
It reads prepared parameters and invokes the actual MCP tool.

Usage:
    # Step 1: Generate parameters
    python3 create_km_doc_mcp_invoke.py diagram.drawio 2733918143

    # Step 2: From Claude's MCP context, call this invoker:
    python3 invoke_km_mcp_directly.py workflow-diagram_mcp_params.json

Or, directly in Claude's context, use the MCP tool:
    Tool: mcp_tool_km_user_add_collaboration_json_content_by_sso
    Parameters: Load from JSON file
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional


def invoke_mcp_tool(title: str, content: str, parent_id: str) -> Dict[str, Any]:
    """
    ⚠️ THIS IS THE CRITICAL FUNCTION THAT MUST RUN IN CLAUDE'S MCP CONTEXT

    When this function is called from within Claude's MCP context,
    it will trigger the actual MCP tool invocation.
    """

    print(f"\n{'='*70}")
    print(f"🚀 INVOKING MCP TOOL - REAL DOCUMENT CREATION")
    print(f"{'='*70}")
    print(f"\n📋 Tool Information:")
    print(f"   Server: km_user")
    print(f"   Tool: mcp_tool_km_user_add_collaboration_json_content_by_sso")
    print(f"\n📝 Parameters:")
    print(f"   title: {title}")
    print(f"   parentId: {parent_id}")
    print(f"   content: ({len(content):,} bytes)")

    # THIS IS WHERE THE MAGIC HAPPENS
    # In Claude's MCP context, this import will resolve to the actual MCP tool
    try:
        # Try direct import (Claude's context)
        from mcp_tool_km_user_add_collaboration_json_content_by_sso import mcp_tool_km_user_add_collaboration_json_content_by_sso

        print(f"\n🔄 Calling MCP tool...")
        result = mcp_tool_km_user_add_collaboration_json_content_by_sso(
            title=title,
            content=content,
            parentId=parent_id
        )

        return result

    except ImportError as e:
        print(f"\n⚠️ Import Error: {e}")
        print(f"\n❌ CRITICAL: This script MUST be run from within Claude's MCP context!")
        print(f"\nTo fix this:")
        print(f"1. Copy this entire output")
        print(f"2. Go to Claude and provide this message")
        print(f"3. Ask Claude to invoke the MCP tool with the parameters shown above")
        print(f"4. Claude will call: mcp_tool_km_user_add_collaboration_json_content_by_sso")
        raise


def main():
    """Main entry point"""

    if len(sys.argv) < 2:
        print(__doc__)
        print("\n❌ Usage: python3 invoke_km_mcp_directly.py <params_file.json>")
        sys.exit(1)

    params_file = Path(sys.argv[1])

    if not params_file.exists():
        print(f"❌ Error: File not found: {params_file}")
        sys.exit(1)

    try:
        with open(params_file, 'r', encoding='utf-8') as f:
            params = json.load(f)

        # Extract parameters
        title = params.get('title')
        content = params.get('content')
        parent_id = params.get('parentId')

        if not all([title, content, parent_id]):
            print(f"❌ Error: Missing required parameters in {params_file}")
            print(f"   Required: title, content, parentId")
            sys.exit(1)

        # Invoke the MCP tool
        result = invoke_mcp_tool(title, content, parent_id)

        # Display result
        print(f"\n{'='*70}")
        print(f"✨ SUCCESS - Document Created!")
        print(f"{'='*70}")
        print(f"\n📋 Result:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        # Extract key information
        if isinstance(result, dict):
            doc_id = result.get('contentId') or result.get('id')
            if doc_id:
                url = f"https://km.sankuai.com/collabpage/{doc_id}"
                print(f"\n🔗 Document URL: {url}")

        print(f"\n{'='*70}\n")
        return 0

    except json.JSONDecodeError:
        print(f"❌ Error: Invalid JSON in {params_file}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())

