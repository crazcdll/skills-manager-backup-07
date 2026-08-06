#!/bin/bash
################################################################################
# Deploy draw.io diagrams to KM (Meituan Knowledge Management) 学城
#
# Complete 4-step workflow:
#   1. Verify .drawio file exists
#   2. Convert .drawio to PNG using drawio CLI
#   3. Generate Markdown with embedded XML
#   4. Create KM document using km create
#
# Usage:
#   ./deploy-drawio-to-km.sh <diagram.drawio> [output.md] [title] [parent_id]
#
# Examples:
#   ./deploy-drawio-to-km.sh hpx-build-workflow.drawio
#   ./deploy-drawio-to-km.sh hpx-build-workflow.drawio hpx-build.md "HPX Build System" 2748666799
#   ./deploy-drawio-to-km.sh --help
#
# Prerequisites:
#   - drawio: npm install -g drawio OR brew install drawio
#   - km CLI: git clone and setup ~/.meituan-local-tools
#   - Python 3.6+
#   - km environment: source ~/.meituan-local-tools/.venv/bin/activate
#
# Author: draw.io Skill v2.2
# Last Updated: 2026-03-02
################################################################################

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
DRAWIO_FILE="${1:-.draw-io-workflow.drawio}"
OUTPUT_MD="${2:-diagram-doc.md}"
KM_TITLE="${3:-System Diagram}"
KM_PARENT_ID="${4:-2748666799}"

# Helper functions
print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_step() {
    echo -e "${YELLOW}⏳ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ Error: $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

show_help() {
    cat << 'EOF'
Draw.io to KM Complete Workflow Deployment Script

USAGE:
    ./deploy-drawio-to-km.sh [OPTIONS] <diagram.drawio>

ARGUMENTS:
    diagram.drawio       Path to .drawio file (required first argument)
    output.md           Output Markdown file (default: diagram-doc.md)
    title               KM document title (default: System Diagram)
    parent_id           Parent document ID in KM (default: 2748666799)

OPTIONS:
    -h, --help          Show this help message and exit
    -d, --dry-run       Show what would be done without executing
    -v, --verbose       Show detailed output
    --no-png            Skip PNG conversion
    --no-create-km      Skip KM document creation (only generate markdown)

ENVIRONMENT VARIABLES:
    DRAWIO_BIN          Path to drawio binary (default: drawio)
    KM_PARENT_ID        Default parent document ID for KM

EXAMPLES:
    # Basic usage with defaults
    ./deploy-drawio-to-km.sh my-diagram.drawio

    # Full workflow with custom parameters
    ./deploy-drawio-to-km.sh \
        my-diagram.drawio \
        my-doc.md \
        "My System Architecture" \
        2748666799

    # Only generate markdown (skip PNG and KM creation)
    ./deploy-drawio-to-km.sh my-diagram.drawio --no-png --no-create-km

    # Dry run to see what would happen
    ./deploy-drawio-to-km.sh my-diagram.drawio --dry-run

PREREQUISITES:
    1. drawio CLI:
       npm install -g drawio
       OR
       brew install drawio

    2. KM tools setup:
       git clone ssh://git@git.sankuai.com/waimb/waimai-ai-tools.git ~/.meituan-local-tools
       cd ~/.meituan-local-tools && bash setup.sh

    3. Activate KM environment before running:
       source ~/.meituan-local-tools/.venv/bin/activate

WORKFLOW STEPS:
    1. Verify .drawio file exists
    2. Convert .drawio to PNG using drawio CLI
    3. Generate Markdown with embedded XML
    4. Create KM document using km create

OUTPUT:
    • Diagram file: {drawio_file}
    • PNG file: {drawio_file%.drawio}.drawio.png
    • Markdown file: {output_md}
    • KM Document: https://km.sankuai.com/page/{DOC_ID}

TROUBLESHOOTING:
    - drawio: command not found
      → Install: npm install -g drawio OR brew install drawio

    - km: command not found
      → Activate: source ~/.meituan-local-tools/.venv/bin/activate

    - PNG not generated
      → Check .drawio file is valid XML: xmllint --noout diagram.drawio

    - KM auth error
      → Open https://km.sankuai.com in browser and log in

DOCUMENTATION:
    See .catpaw/skills/draw-io/SKILL.md section 11 for complete documentation
EOF
}

# Parse command line arguments
VERBOSE=0
DRY_RUN=0
SKIP_PNG=0
SKIP_KM=0

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--verbose)
            VERBOSE=1
            shift
            ;;
        -d|--dry-run)
            DRY_RUN=1
            shift
            ;;
        --no-png)
            SKIP_PNG=1
            shift
            ;;
        --no-create-km)
            SKIP_KM=1
            shift
            ;;
        -*)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
        *)
            # First positional argument is the diagram file
            if [ "$DRAWIO_FILE" = ".draw-io-workflow.drawio" ]; then
                DRAWIO_FILE="$1"
            fi
            shift
            ;;
    esac
done

print_header "📊 Draw.io to KM Complete Workflow Deployment"

# Display configuration
echo -e "${BLUE}Configuration:${NC}"
echo "  Diagram File:    $DRAWIO_FILE"
echo "  Markdown File:   $OUTPUT_MD"
echo "  KM Title:        $KM_TITLE"
echo "  Parent Doc ID:   $KM_PARENT_ID"
echo "  Verbose:         $([ $VERBOSE -eq 1 ] && echo 'Yes' || echo 'No')"
echo "  Dry Run:         $([ $DRY_RUN -eq 1 ] && echo 'Yes' || echo 'No')"
echo ""

# ============================================================================
# Step 1: Verify .drawio file exists
# ============================================================================

print_step "Step 1: Verifying diagram file exists..."

if [ ! -f "$DRAWIO_FILE" ]; then
    print_error "Diagram file not found: $DRAWIO_FILE"
    echo ""
    echo "Make sure the file exists and the path is correct."
    exit 1
fi

DRAWIO_ABS_PATH="$(cd "$(dirname "$DRAWIO_FILE")" && pwd)/$(basename "$DRAWIO_FILE")"
print_success "Found diagram file: $DRAWIO_ABS_PATH"

# Validate XML
if ! xmllint --noout "$DRAWIO_FILE" 2>/dev/null; then
    print_error "Invalid XML in $DRAWIO_FILE"
    echo "  Hint: Open in draw.io and save to fix formatting"
    exit 1
fi
print_success "XML validation passed"

# ============================================================================
# Step 2: Convert .drawio to PNG
# ============================================================================

if [ $SKIP_PNG -eq 0 ]; then
    print_step "Step 2: Converting .drawio to PNG..."

    PNG_FILE="${DRAWIO_FILE%.drawio}.drawio.png"

    # Check if drawio is installed
    if ! command -v drawio &> /dev/null; then
        print_error "drawio CLI not found. Install with: npm install -g drawio"
        exit 1
    fi

    if [ $DRY_RUN -eq 0 ]; then
        drawio -x -f png -s 2 -t -o "$PNG_FILE" "$DRAWIO_FILE" 2>/dev/null || {
            print_error "Failed to convert PNG. Check file format."
            exit 1
        }
        print_success "PNG created: $PNG_FILE"
    else
        print_info "[DRY RUN] Would execute: drawio -x -f png -s 2 -t -o \"$PNG_FILE\" \"$DRAWIO_FILE\""
    fi
else
    print_info "Skipping PNG conversion (--no-png)"
fi

# ============================================================================
# Step 3: Generate Markdown with embedded XML
# ============================================================================

print_step "Step 3: Generating Markdown with embedded XML..."

if [ $DRY_RUN -eq 0 ]; then
    # Check if Python script exists
    CREATE_MD_SCRIPT="$SCRIPT_DIR/create_drawio_markdown.py"
    if [ ! -f "$CREATE_MD_SCRIPT" ]; then
        print_error "Python script not found: $CREATE_MD_SCRIPT"
        exit 1
    fi

    # Execute Python script
    python3 "$CREATE_MD_SCRIPT" \
        "$DRAWIO_FILE" \
        -o "$OUTPUT_MD" \
        -t "$KM_TITLE" || {
        print_error "Failed to generate Markdown"
        exit 1
    }
    print_success "Markdown created: $OUTPUT_MD"
else
    print_info "[DRY RUN] Would execute: python3 $SCRIPT_DIR/create_drawio_markdown.py \"$DRAWIO_FILE\" -o \"$OUTPUT_MD\" -t \"$KM_TITLE\""
fi

# ============================================================================
# Step 4: Create KM document
# ============================================================================

if [ $SKIP_KM -eq 0 ]; then
    print_step "Step 4: Creating KM document..."

    # Check if km is available
    if ! command -v km &> /dev/null; then
        print_error "km CLI not found or not activated"
        echo ""
        echo "Activate with:"
        echo "  source ~/.meituan-local-tools/.venv/bin/activate"
        exit 1
    fi

    if [ $DRY_RUN -eq 0 ]; then
        # Create KM document with explicit error handling
        if KM_OUTPUT=$(km create --title "$KM_TITLE" --file "$OUTPUT_MD" --parent "$KM_PARENT_ID" 2>&1); then
            # Success case: Try multiple patterns to extract document ID
            KM_DOC_ID=$(echo "$KM_OUTPUT" | grep -oP 'page/\K\d+|ID:\s*\K\d+|Document ID:\s*\K\d+' | head -1)

            if [ -n "$KM_DOC_ID" ] && [ "$KM_DOC_ID" != "" ]; then
                print_success "KM document created successfully"
                echo -e "${GREEN}📄 Document URL: https://km.sankuai.com/page/$KM_DOC_ID${NC}"
            else
                print_success "KM document created (couldn't extract ID from output)"
                echo "  Full output:"
                echo "$KM_OUTPUT" | sed 's/^/    /'
            fi
        else
            # Failure case: Show detailed error information
            KM_EXIT_CODE=$?
            print_error "km create failed with exit code $KM_EXIT_CODE"
            echo ""
            echo "Error output (first 20 lines):"
            echo "$KM_OUTPUT" | head -20 | sed 's/^/    /'
            echo ""
            echo "Troubleshooting:"
            echo "  1. Verify km CLI is activated: source ~/.meituan-local-tools/.venv/bin/activate"
            echo "  2. Check network connectivity: ping km.sankuai.com"
            echo "  3. Verify markdown file exists: test -f \"$OUTPUT_MD\" && echo OK || echo NOT FOUND"
            echo "  4. Check parent document ID is correct: $KM_PARENT_ID"
            exit 1
        fi
    else
        print_info "[DRY RUN] Would execute: km create --title \"$KM_TITLE\" --file \"$OUTPUT_MD\" --parent \"$KM_PARENT_ID\""
    fi
else
    print_info "Skipping KM document creation (--no-create-km)"
fi

# ============================================================================
# Step 5: Verify XML Insertion (Optional, recommended for high-priority docs)
# ============================================================================

if [ $SKIP_KM -eq 0 ] && [ -n "$KM_DOC_ID" ] && [ "$KM_DOC_ID" != "" ] && [ $VERBOSE -eq 1 ]; then
    print_step "Step 5: Verifying XML was correctly inserted (verbose mode)..."

    # Retrieve document to verify
    if km get "$KM_DOC_ID" > /tmp/km_verify.txt 2>/dev/null; then
        # Check code block structure
        if grep -q '```xml' /tmp/km_verify.txt; then
            print_success "XML code block opening tag found"
        else
            print_error "WARNING: XML code block opening tag NOT found"
        fi

        # Check XML presence
        if grep -q '<mxfile' /tmp/km_verify.txt; then
            print_success "mxfile element preserved"
        else
            print_error "WARNING: mxfile element NOT found"
        fi

        # Check for excessive HTML encoding
        if grep -q "&lt;mxfile" /tmp/km_verify.txt; then
            print_error "WARNING: Possible HTML entity encoding detected"
        else
            print_success "No excessive HTML entity encoding detected"
        fi

        rm -f /tmp/km_verify.txt
    fi
fi

# ============================================================================
# Summary
# ============================================================================

print_header "✅ Workflow Complete!"

echo -e "${GREEN}Generated files:${NC}"
echo "  • Diagram XML:    $DRAWIO_FILE"
if [ $SKIP_PNG -eq 0 ]; then
    echo "  • Diagram PNG:    ${DRAWIO_FILE%.drawio}.drawio.png"
fi
echo "  • Markdown Doc:   $OUTPUT_MD"
if [ $SKIP_KM -eq 0 ]; then
    if [ -n "$KM_DOC_ID" ] && [ "$KM_DOC_ID" != "" ]; then
        echo "  • KM Doc URL:     https://km.sankuai.com/page/$KM_DOC_ID"
    else
        echo "  • KM Document:    Created (check km.sankuai.com)"
    fi
fi

echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "  1. Review PNG output for quality"
if [ $SKIP_KM -eq 0 ]; then
    echo "  2. Share KM document URL with team"
    echo "  3. Update Markdown as needed"
    echo "  4. Re-run this script to update KM document"
else
    echo "  2. Review generated Markdown"
    echo "  3. Use: km create --title \"...\" --file \"$OUTPUT_MD\" --parent $KM_PARENT_ID"
fi

echo ""
echo -e "${BLUE}Documentation: .catpaw/skills/draw-io/SKILL.md section 11${NC}"
echo ""

