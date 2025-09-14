#!/usr/bin/env python3
"""
GitHub Release Creation Script
Automates the process of creating releases for the Ansys MCP Server.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

def run_command(cmd: List[str], capture_output: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=capture_output, text=True)
    if result.returncode != 0:
        print(f"Error running command: {' '.join(cmd)}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)
    return result

def get_current_version() -> str:
    """Get the current version from the package."""
    try:
        result = run_command(["python", "-c", "import ansys_mcp_server; print(ansys_mcp_server.__version__)"])
        return result.stdout.strip()
    except:
        # Fallback to reading from setup.py or pyproject.toml
        return "0.1.0"

def validate_version(version: str) -> bool:
    """Validate version format (semantic versioning)."""
    import re
    pattern = r'^v?\d+\.\d+\.\d+(-[a-zA-Z0-9]+)*$'
    return bool(re.match(pattern, version))

def generate_changelog(version: str, since_tag: Optional[str] = None) -> str:
    """Generate changelog from git commits."""
    if since_tag:
        cmd = ["git", "log", f"{since_tag}..HEAD", "--pretty=format:- %s (%h)"]
    else:
        cmd = ["git", "log", "--pretty=format:- %s (%h)", "-10"]  # Last 10 commits
    
    result = run_command(cmd)
    
    changelog = f"""## Changes in {version}

### Commits
{result.stdout}

### Installation
```bash
pip install ansys-mcp-server=={version.lstrip('v')}
```

### Docker
```bash
docker pull ghcr.io/yourusername/ansys-mcp-server:{version}
```
"""
    
    return changelog

def create_git_tag(version: str, message: str):
    """Create and push git tag."""
    tag_name = f"v{version.lstrip('v')}"
    
    # Create annotated tag
    run_command(["git", "tag", "-a", tag_name, "-m", message])
    
    # Push tag
    run_command(["git", "push", "origin", tag_name])
    
    print(f"Created and pushed tag: {tag_name}")
    return tag_name

def build_package():
    """Build the Python package."""
    print("Building package...")
    
    # Clean previous builds
    run_command(["rm", "-rf", "build", "dist", "*.egg-info"], capture_output=False)
    
    # Build package
    run_command(["python", "-m", "build"])
    
    # Verify build
    dist_files = list(Path("dist").glob("*"))
    print(f"Built files: {[f.name for f in dist_files]}")
    
    return dist_files

def run_tests():
    """Run test suite before release."""
    print("Running tests...")
    run_command(["pytest", "tests/", "-v"])
    print("All tests passed!")

def create_github_release(tag_name: str, changelog: str, prerelease: bool = False):
    """Create GitHub release using GitHub CLI."""
    print(f"Creating GitHub release for {tag_name}...")
    
    cmd = [
        "gh", "release", "create", tag_name,
        "--title", f"Release {tag_name}",
        "--notes", changelog
    ]
    
    if prerelease:
        cmd.append("--prerelease")
    
    # Add distribution files
    dist_files = list(Path("dist").glob("*"))
    for file in dist_files:
        cmd.append(str(file))
    
    run_command(cmd, capture_output=False)
    print(f"GitHub release created: {tag_name}")

def update_docker_image(version: str):
    """Build and push Docker image."""
    tag_name = f"v{version.lstrip('v')}"
    
    print(f"Building Docker image for {tag_name}...")
    
    # Create Dockerfile if it doesn't exist
    dockerfile_content = """FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    git \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install the package
RUN pip install -e .

# Create non-root user
RUN useradd --create-home --shell /bin/bash ansys
USER ansys

# Expose port (if needed for HTTP mode)
EXPOSE 8000

# Default command
CMD ["ansys-mcp-server"]
"""
    
    dockerfile_path = Path("Dockerfile")
    if not dockerfile_path.exists():
        with open(dockerfile_path, 'w') as f:
            f.write(dockerfile_content)
    
    # Build Docker image
    image_name = f"ghcr.io/yourusername/ansys-mcp-server"
    run_command([
        "docker", "build", 
        "-t", f"{image_name}:{tag_name}",
        "-t", f"{image_name}:latest",
        "."
    ])
    
    # Push to registry
    run_command(["docker", "push", f"{image_name}:{tag_name}"])
    run_command(["docker", "push", f"{image_name}:latest"])
    
    print(f"Docker image pushed: {image_name}:{tag_name}")

def publish_to_pypi(test_pypi: bool = False):
    """Publish package to PyPI."""
    if test_pypi:
        print("Publishing to Test PyPI...")
        repository = "--repository testpypi"
        url = "https://test.pypi.org/project/ansys-mcp-server/"
    else:
        print("Publishing to PyPI...")
        repository = ""
        url = "https://pypi.org/project/ansys-mcp-server/"
    
    cmd = ["python", "-m", "twine", "upload"]
    if repository:
        cmd.extend(repository.split())
    cmd.append("dist/*")
    
    run_command(cmd)
    print(f"Package published to {url}")

def main():
    """Main release automation script."""
    parser = argparse.ArgumentParser(description="Create release for Ansys MCP Server")
    parser.add_argument("version", help="Version to release (e.g., 1.0.0)")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument("--skip-build", action="store_true", help="Skip building package")
    parser.add_argument("--skip-docker", action="store_true", help="Skip Docker image")
    parser.add_argument("--skip-pypi", action="store_true", help="Skip PyPI publication")
    parser.add_argument("--test-pypi", action="store_true", help="Publish to Test PyPI")
    parser.add_argument("--prerelease", action="store_true", help="Mark as prerelease")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    args = parser.parse_args()
    
    # Validate version
    if not validate_version(args.version):
        print(f"Invalid version format: {args.version}")
        sys.exit(1)
    
    version = args.version.lstrip('v')
    tag_name = f"v{version}"
    
    print(f"Creating release for version {version}")
    print(f"Dry run: {args.dry_run}")
    
    if args.dry_run:
        print("DRY RUN - No actual changes will be made")
        return
    
    try:
        # Step 1: Run tests
        if not args.skip_tests:
            run_tests()
        
        # Step 2: Build package
        if not args.skip_build:
            build_package()
        
        # Step 3: Generate changelog
        changelog = generate_changelog(version)
        print("Generated changelog:")
        print(changelog)
        
        # Step 4: Create git tag
        create_git_tag(version, f"Release {tag_name}")
        
        # Step 5: Create GitHub release
        create_github_release(tag_name, changelog, args.prerelease)
        
        # Step 6: Build and push Docker image
        if not args.skip_docker:
            update_docker_image(version)
        
        # Step 7: Publish to PyPI
        if not args.skip_pypi:
            publish_to_pypi(args.test_pypi)
        
        print(f"\n🎉 Release {tag_name} completed successfully!")
        print(f"- GitHub: https://github.com/yourusername/ansys-mcp-server/releases/tag/{tag_name}")
        if not args.skip_pypi:
            if args.test_pypi:
                print(f"- Test PyPI: https://test.pypi.org/project/ansys-mcp-server/")
            else:
                print(f"- PyPI: https://pypi.org/project/ansys-mcp-server/")
        if not args.skip_docker:
            print(f"- Docker: ghcr.io/yourusername/ansys-mcp-server:{tag_name}")
    
    except Exception as e:
        print(f"❌ Release failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()