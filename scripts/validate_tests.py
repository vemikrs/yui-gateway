#!/usr/bin/env python3
"""
Test validation script for YuiGateway
Validates test file structure without running tests
"""

import sys
from pathlib import Path


def check_file_syntax(filepath):
    """Check if a Python file has valid syntax"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            compile(f.read(), filepath, 'exec')
        return True, None
    except SyntaxError as e:
        return False, str(e)


def main():
    """Validate all test files"""
    project_root = Path(__file__).parent.parent
    test_files = [
        project_root / "tests" / "conftest.py",
        project_root / "tests" / "test_settings.py",
        project_root / "tests" / "test_auth.py",
        project_root / "tests" / "test_azure_proxy.py",
        project_root / "tests" / "test_routes.py",
    ]
    
    gateway_files = [
        project_root / "gateway" / "__init__.py",
        project_root / "gateway" / "settings.py",
        project_root / "gateway" / "auth.py",
        project_root / "gateway" / "azure_proxy.py",
        project_root / "gateway" / "routes.py",
    ]
    
    all_files = test_files + gateway_files
    
    print("=" * 60)
    print("YuiGateway Test Validation")
    print("=" * 60)
    print()
    
    errors = []
    
    for filepath in all_files:
        if not filepath.exists():
            print(f"❌ {filepath.name}: File not found")
            errors.append(filepath.name)
            continue
        
        valid, error = check_file_syntax(filepath)
        if valid:
            print(f"✅ {filepath.name}: Syntax OK")
        else:
            print(f"❌ {filepath.name}: Syntax Error")
            print(f"   {error}")
            errors.append(filepath.name)
    
    print()
    print("=" * 60)
    
    if errors:
        print(f"❌ Validation failed: {len(errors)} file(s) with errors")
        print(f"   Files: {', '.join(errors)}")
        sys.exit(1)
    else:
        print("✅ All files validated successfully!")
        print()
        print("Test files are ready to run.")
        print("Run tests with: pytest")
        sys.exit(0)


if __name__ == "__main__":
    main()
