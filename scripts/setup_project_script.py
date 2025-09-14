#!/usr/bin/env python3
"""
Project Setup Script
Initialize the Ansys MCP Server project structure and configuration.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

def run_command(cmd: List[str], cwd: Path = None) -> bool:
    """Run a command and return success status."""
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Warning: Command failed: {' '.join(cmd)}")
            print(f"Error: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Error running command {' '.join(cmd)}: {e}")
        return False

def create_directory_structure():
    """Create the project directory structure."""
    
    directories = [
        "ansys_mcp_server",
        "tests/unit", 
        "tests/integration",
        "tests/fixtures",
        "examples",
        "docs",
        "scripts",
        ".github/workflows",
        ".github/ISSUE_TEMPLATE",
        ".github/PULL_REQUEST_TEMPLATE"
    ]
    
    print("Creating directory structure...")
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {directory}/")

def create_init_files():
    """Create __init__.py files and version info."""
    
    # Main package __init__.py
    init_content = '''"""
Ansys MCP Server

A Model Context Protocol server for Ansys simulation software.
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .ansys_mcp_server import main, AnsysInterface, server

__all__ = ["main", "AnsysInterface", "server"]
'''
    
    with open("ansys_mcp_server/__init__.py", "w") as f:
        f.write(init_content)
    
    # Tests __init__.py
    Path("tests/__init__.py").touch()
    Path("tests/unit/__init__.py").touch()
    Path("tests/integration/__init__.py").touch()

def create_github_templates():
    """Create GitHub issue and PR templates."""
    
    # Bug report template
    bug_template = """---
name: Bug report
about: Create a report to help us improve
title: '[BUG] '
labels: 'bug'
assignees: ''

---

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected behavior**
A clear and concise description of what you expected to happen.

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Environment:**
 - OS: [e.g. Windows 10, Ubuntu 20.04]
 - Python version: [e.g. 3.9.0]
 - Ansys version: [e.g. 2023 R1]
 - PyAnsys packages: [e.g. ansys-fluent-core==0.15.0]

**Additional context**
Add any other context about the problem here.
"""
    
    with open(".github/ISSUE_TEMPLATE/bug_report.md", "w") as f:
        f.write(bug_template)
    
    # Feature request template
    feature_template = """---
name: Feature request
about: Suggest an idea for this project
title: '[FEATURE] '
labels: 'enhancement'
assignees: ''

---

**Is your feature request related to a problem? Please describe.**
A clear and concise description of what the problem is. Ex. I'm always frustrated when [...]

**Describe the solution you'd like**
A clear and concise description of what you want to happen.

**Describe alternatives you've considered**
A clear and concise description of any alternative solutions or features you've considered.

**Additional context**
Add any other context or screenshots about the feature request here.

**Ansys Products**
Which Ansys products would this feature support?
- [ ] Fluent
- [ ] MAPDL
- [ ] Mechanical
- [ ] CFX
- [ ] Other: _______
"""
    
    with open(".github/ISSUE_TEMPLATE/feature_request.md", "w") as f:
        f.write(feature_template)
    
    # Pull request template
    pr_template = """## Description

Brief description of the changes in this PR.

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Code refactoring
- [ ] Performance improvement
- [ ] Test improvement

## Ansys Products Affected

- [ ] Fluent
- [ ] MAPDL  
- [ ] Mechanical
- [ ] Geometry
- [ ] Other: _______

## How Has This Been Tested?

- [ ] Unit tests
- [ ] Integration tests
- [ ] Manual testing
- [ ] Tested with real Ansys installation

## Checklist

- [ ] My code follows the style guidelines of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published in downstream modules

## Additional Notes

Add any additional notes or context about the PR here.
"""
    
    with open(".github/pull_request_template.md", "w") as f:
        f.write(pr_template)

def create_docs_structure():
    """Create basic documentation structure."""
    
    docs_files = {
        "docs/index.md": """# Ansys MCP Server Documentation

Welcome to the Ansys MCP Server documentation!

## Quick Start

1. [Installation](installation.md)
2. [Configuration](configuration.md) 
3. [Usage Examples](examples.md)
4. [API Reference](api.md)

## Ansys Products

- [Fluent Integration](fluent.md)
- [MAPDL Integration](mapdl.md)
- [Mechanical Integration](mechanical.md)
- [Geometry Integration](geometry.md)

## Advanced Topics

- [Custom Tools](custom-tools.md)
- [Performance Tuning](performance.md)
- [Troubleshooting](troubleshooting.md)
""",
        
        "docs/installation.md": """# Installation

## Prerequisites

- Python 3.8+
- Ansys software
- PyAnsys packages

## Install from PyPI

```bash
pip install ansys-mcp-server
```

## Install from Source

```bash
git clone https://github.com/yourusername/ansys-mcp-server.git
cd ansys-mcp-server
pip install -e .
```

## Ansys Configuration

Set your Ansys installation path:

```bash
export ANSYS_ROOT="/path/to/ansys"
```
""",
        
        "docs/examples.md": """# Usage Examples

## Basic Usage

```python
# Check Ansys status
result = await call_tool("check_ansys_status", {})

# Create Fluent session
session = await call_tool("create_fluent_session", {
    "precision": "double",
    "dimension": "3d"
})
```

## Advanced Workflows

See the [examples directory](../examples/) for complete workflows.
"""
    }
    
    for file_path, content in docs_files.items():
        with open(file_path, "w") as f:
            f.write(content)

def setup_git_repository():
    """Initialize git repository and set up initial commit."""
    
    if not Path(".git").exists():
        print("Initializing git repository...")
        
        if not run_command(["git", "init"]):
            print("Failed to initialize git repository")
            return False
        
        # Set up initial branch
        run_command(["git", "branch", "-M", "main"])
        
        # Add all files
        run_command(["git", "add", "."])
        
        # Create initial commit
        run_command(["git", "commit", "-m", "Initial commit: Ansys MCP Server project setup"])
        
        print("Git repository initialized with initial commit")
        return True
    else:
        print("Git repository already exists")
        return True

def setup_pre_commit():
    """Set up pre-commit hooks."""
    
    pre_commit_config = """repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict
      
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.8
        
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
"""
    
    with open(".pre-commit-config.yaml", "w") as f:
        f.write(pre_commit_config)
    
    print("Pre-commit configuration created")

def create_makefile():
    """Create Makefile for common tasks."""
    
    makefile_content = """# Ansys MCP Server Makefile

.PHONY: help install dev-install test lint format clean build release

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\\033[36m%-15s\\033[0m %s\\n", $$1, $$2}'

install:  ## Install the package
	pip install -e .

dev-install:  ## Install development dependencies
	pip install -e .[dev]
	pre-commit install

test:  ## Run tests
	pytest tests/ -v

test-cov:  ## Run tests with coverage
	pytest tests/ --cov=ansys_mcp_server --cov-report=html --cov-report=term

lint:  ## Run linting
	flake8 ansys_mcp_server.py tests/
	mypy ansys_mcp_server.py

format:  ## Format code
	black ansys_mcp_server.py tests/ examples/
	
check:  ## Run all checks (lint + test)
	make lint
	make test

clean:  ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build:  ## Build package
	python -m build

release:  ## Create release (use VERSION=x.x.x)
	python scripts/create_github_release.py $(VERSION)

docker-build:  ## Build Docker image
	docker build -t ansys-mcp-server .

docker-run:  ## Run Docker container
	docker run -it --rm ansys-mcp-server

serve-docs:  ## Serve documentation locally
	python -m http.server 8000 --directory docs/
"""
    
    with open("Makefile", "w") as f:
        f.write(makefile_content)

def main():
    """Main setup function."""
    
    print("🚀 Setting up Ansys MCP Server project...\n")
    
    # Step 1: Create directory structure
    create_directory_structure()
    
    # Step 2: Create init files
    print("\nCreating package files...")
    create_init_files()
    
    # Step 3: Create GitHub templates
    print("Creating GitHub templates...")
    create_github_templates()
    
    # Step 4: Create documentation
    print("Creating documentation structure...")
    create_docs_structure()
    
    # Step 5: Set up pre-commit
    print("Setting up pre-commit hooks...")
    setup_pre_commit()
    
    # Step 6: Create Makefile
    print("Creating Makefile...")
    create_makefile()
    
    # Step 7: Set up git repository
    print("\nSetting up git repository...")
    setup_git_repository()
    
    print("\n✅ Project setup complete!")
    print("\nNext steps:")
    print("1. Update personal information in setup.py and other files")
    print("2. Set up your GitHub repository:")
    print("   git remote add origin https://github.com/yourusername/ansys-mcp-server.git")
    print("3. Install development dependencies:")
    print("   make dev-install")
    print("4. Run tests to verify setup:")
    print("   make test")
    print("5. Create your first commit:")
    print("   git push -u origin main")
    print("\n🎉 Happy coding!")

if __name__ == "__main__":
    main()