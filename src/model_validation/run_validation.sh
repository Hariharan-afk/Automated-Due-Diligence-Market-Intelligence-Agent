#!/bin/bash

# validation/run_validation.sh
# Quick validation runner script

set -e  # Exit on error

echo "════════════════════════════════════════════════════════════════"
echo "🔬 MODEL VALIDATION PIPELINE"
echo "════════════════════════════════════════════════════════════════"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
MODE=${1:-full}
QUICK_TEST=false
SKIP_DATA_GEN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_TEST=true
            shift
            ;;
        --skip-data-gen)
            SKIP_DATA_GEN=true
            shift
            ;;
        --help)
            echo "Usage: ./run_validation.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --quick           Run only 3 test cases (fast)"
            echo "  --skip-data-gen   Skip test data generation"
            echo "  --help            Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./run_validation.sh                    # Full validation"
            echo "  ./run_validation.sh --quick            # Quick test"
            echo "  ./run_validation.sh --skip-data-gen    # Skip data generation"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

# Check if Qdrant is running
echo ""
echo "📡 Checking Qdrant connection..."
if ! curl -s http://localhost:6333/collections > /dev/null 2>&1; then
    echo -e "${RED}❌ Qdrant is not running!${NC}"
    echo "Start Qdrant with: docker run -p 6333:6333 qdrant/qdrant"
    exit 1
fi
echo -e "${GREEN}✅ Qdrant is running${NC}"

# Generate test data if needed
if [ "$SKIP_DATA_GEN" = false ]; then
    echo ""
    echo "📊 Generating test data..."
    python test_data/generate_and_store.py
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Test data generation failed${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  Skipping test data generation${NC}"
fi

# Generate test dataset
echo ""
echo "📝 Generating test dataset..."
python validation/test_dataset.py
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Test dataset generation failed${NC}"
    exit 1
fi

# Run validation
echo ""
if [ "$QUICK_TEST" = true ]; then
    echo "🚀 Running QUICK validation (3 test cases)..."
    python -c "
from validation.run_validation import ValidationPipeline
import sys

pipeline = ValidationPipeline()
results = pipeline.run_all_tests(limit=3)
summary = pipeline.compute_summary_statistics()
acceptance = pipeline.check_acceptance_criteria(summary)

# Save results
pipeline.save_results()

# Generate report
from validation.validation_report import ValidationReport
report = ValidationReport(results, summary, acceptance)
report.generate_html_report()

# Print summary
print('\n' + '='*70)
print('📊 VALIDATION SUMMARY')
print('='*70)
print(f'Success Rate: {summary[\"success_rate\"]:.1%}')
print(f'Avg Quality Score: {summary.get(\"avg_overall_score\", 0):.2%}')
print(f'Avg Execution Time: {summary.get(\"avg_execution_time\", 0):.2f}s')
print(f'Acceptance Criteria: {\"✅ MET\" if acceptance[\"all_criteria_met\"] else \"❌ NOT MET\"}')
print('='*70)

sys.exit(0 if acceptance['all_criteria_met'] else 1)
"
else
    echo "🚀 Running FULL validation (all test cases)..."
    python validation/run_validation.py
fi

VALIDATION_EXIT_CODE=$?

# Results summary
echo ""
echo "════════════════════════════════════════════════════════════════"
if [ $VALIDATION_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ VALIDATION PASSED${NC}"
else
    echo -e "${RED}❌ VALIDATION FAILED${NC}"
fi
echo "════════════════════════════════════════════════════════════════"

# Find and display report files
echo ""
echo "📄 Generated Reports:"
ls -lht validation/reports/ 2>/dev/null | head -5

# Display latest HTML report location
LATEST_HTML=$(ls -t validation/reports/report_*.html 2>/dev/null | head -1)
if [ ! -z "$LATEST_HTML" ]; then
    echo ""
    echo "🌐 View HTML report:"
    echo "   open $LATEST_HTML"
fi

exit $VALIDATION_EXIT_CODE