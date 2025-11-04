#!/bin/bash
# Test runner script for YuiGateway
# Runs all tests with coverage reporting

set -e

echo "================================"
echo "YuiGateway Test Suite"
echo "================================"
echo ""

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest is not installed"
    echo "Please install dependencies:"
    echo "  poetry install"
    echo "  # or"
    echo "  pip install pytest pytest-asyncio pytest-mock pytest-cov"
    exit 1
fi

echo "✅ pytest found"
echo ""

# Check if in correct directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Not in project root directory"
    echo "Please run this script from the project root"
    exit 1
fi

echo "✅ In project root directory"
echo ""

# Set PYTHONPATH to include project root
export PYTHONPATH="${PWD}:${PYTHONPATH}"
echo "PYTHONPATH set to: ${PYTHONPATH}"
echo ""

# Run tests with coverage
echo "Running tests with coverage..."
echo "================================"
echo ""

pytest -v \
    --cov=gateway \
    --cov-report=term-missing \
    --cov-report=html \
    --tb=short

echo ""
echo "================================"
echo "Test run complete!"
echo "================================"
echo ""
echo "Coverage report saved to: htmlcov/index.html"
echo ""
echo "To run specific tests:"
echo "  pytest tests/test_routes.py"
echo "  pytest tests/test_auth.py -v"
echo "  pytest -k test_health"
echo ""
echo "To run with markers:"
echo "  pytest -m unit"
echo "  pytest -m 'not slow'"
echo ""
