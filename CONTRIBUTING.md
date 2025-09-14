# Contributing to Ansys MCP Server

Thank you for your interest in contributing to the Ansys MCP Server! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Process](#contributing-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)

## Code of Conduct

This project adheres to a code of conduct that we expect all contributors to follow. Please be respectful and constructive in all interactions.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- Ansys software installation (for testing)
- Basic knowledge of:
  - Python async/await programming
  - Model Context Protocol (MCP)
  - Ansys software (Fluent, MAPDL, etc.)

### Areas for Contribution

We welcome contributions in several areas:

1. **Core MCP Server Features**
   - New tool implementations
   - Enhanced resource management
   - Performance improvements
   - Error handling

2. **Ansys Product Support**
   - Additional Ansys products (CFX, Icepak, etc.)
   - Enhanced PyAnsys integration
   - Advanced simulation workflows

3. **Documentation**
   - API documentation
   - Usage examples
   - Tutorial content
   - Integration guides

4. **Testing**
   - Unit tests
   - Integration tests
   - Performance tests
   - Mock implementations

5. **DevOps**
   - CI/CD improvements
   - Docker containerization
   - Deployment automation

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/yourusername/ansys-mcp-server.git
cd ansys-mcp-server

# Add the original repository as upstream
git remote add upstream https://github.com/originalowner/ansys-mcp-server.git
```

### 2. Create Development Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install development dependencies
pip install -e .[dev]
```

### 3. Install Pre-commit Hooks

```bash
pre-commit install
```

### 4. Verify Installation

```bash
# Run tests
pytest

# Run linting
black --check ansys_mcp_server.py
flake8 ansys_mcp_server.py

# Run type checking
mypy ansys_mcp_server.py
```

## Contributing Process

### 1. Planning Your Contribution

- **Check existing issues** to see if your idea is already being worked on
- **Open an issue** for discussion before starting major changes
- **Join discussions** on existing issues to coordinate efforts

### 2. Creating a Branch

```bash
# Update your fork
git fetch upstream
git checkout main
git merge upstream/main

# Create feature branch
git checkout -b feature/your-feature-name
```

### 3. Making Changes

- Write clear, concise code following our coding standards
- Include comprehensive tests for new functionality
- Update documentation as needed
- Commit frequently with descriptive messages

### 4. Testing Your Changes

```bash
# Run the full test suite
pytest

# Run specific test files
pytest tests/test_server.py

# Run with coverage
pytest --cov=ansys_mcp_server

# Test with different Python versions (if available)
tox
```

## Coding Standards

### Python Style

We follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) with these tools:

- **Black** for code formatting
- **flake8** for linting
- **mypy** for type checking

### Code Organization

```python
# File structure
ansys_mcp_server/
├── __init__.py           # Main module
├── server.py             # MCP server implementation
├── ansys_interface.py    # Ansys integration
├── tools/                # Individual tool implementations
│   ├── __init__.py
│   ├── fluent_tools.py
│   ├── mapdl_tools.py
│   └── common_tools.py
├── resources/            # Resource handlers
│   ├── __init__.py
│   └── ansys_resources.py
└── utils/                # Utility functions
    ├── __init__.py
    └── helpers.py
```

### Naming Conventions

- **Functions/Variables**: `snake_case`
- **Classes**: `PascalCase`  
- **Constants**: `UPPER_CASE`
- **Private attributes**: `_leading_underscore`

### Documentation

- Use Google-style docstrings
- Include type hints for all function parameters and return values
- Document complex algorithms and business logic

```python
def create_fluent_session(
    precision: str = "double",
    dimension: str = "3d"
) -> Dict[str, Any]:
    """Create a new Ansys Fluent session.
    
    Args:
        precision: Calculation precision ('single' or 'double').
        dimension: Simulation dimension ('2d' or '3d').
        
    Returns:
        Dictionary containing session information and status.
        
    Raises:
        ImportError: If PyFluent is not available.
        RuntimeError: If session creation fails.
    """
```

## Testing

### Test Structure

```
tests/
├── unit/                 # Unit tests
│   ├── test_server.py
│   ├── test_interface.py
│   └── test_tools.py
├── integration/          # Integration tests
│   ├── test_fluent_integration.py
│   └── test_mapdl_integration.py
├── fixtures/            # Test data and fixtures
│   ├── sample_files/
│   └── mock_data.py
└── conftest.py          # Pytest configuration
```

### Writing Tests

- **Unit tests** for individual functions and classes
- **Integration tests** for end-to-end workflows
- **Mock external dependencies** (Ansys software) when needed
- **Use descriptive test names** that explain what is being tested

```python
import pytest
from unittest.mock import Mock, patch

class TestFluentInterface:
    
    @patch('ansys.fluent.core.launch_fluent')
    async def test_create_session_success(self, mock_launch):
        """Test successful Fluent session creation with default parameters."""
        # Arrange
        mock_session = Mock()
        mock_launch.return_value = mock_session
        
        # Act
        result = await create_fluent_session()
        
        # Assert
        assert result["status"] == "success"
        assert result["precision"] == "double"
        mock_launch.assert_called_once()
```

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/unit/test_server.py

# Specific test function
pytest tests/unit/test_server.py::TestMCPServer::test_list_tools

# With coverage
pytest --cov=ansys_mcp_server --cov-report=html

# Skip slow tests
pytest -m "not slow"
```

## Documentation

### Types of Documentation

1. **API Documentation** - Generated from docstrings
2. **User Guide** - How to use the server
3. **Developer Guide** - How to contribute
4. **Examples** - Working code samples

### Writing Documentation

- Use clear, concise language
- Include practical examples
- Keep documentation up-to-date with code changes
- Test all code examples

## Submitting Changes

### 1. Final Checks

Before submitting your pull request:

```bash
# Format code
black ansys_mcp_server.py

# Run lints
flake8 ansys_mcp_server.py

# Type check
mypy ansys_mcp_server.py

# Run tests
pytest

# Check documentation builds
# (if applicable)
```

### 2. Commit Messages

Use clear, descriptive commit messages:

```
feat: add support for Ansys CFX integration

- Implement CFX session management
- Add CFX-specific tools and resources  
- Include comprehensive test coverage
- Update documentation with CFX examples

Closes #123
```

### 3. Pull Request

1. **Push your branch** to your fork
2. **Create pull request** from your branch to `main`
3. **Fill out the PR template** completely
4. **Link related issues** using keywords like "Closes #123"

### 4. Pull Request Template

```markdown
## Description
Brief description of changes made.

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)  
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests pass locally
- [ ] Manual testing performed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No breaking changes (or breaking changes documented)
```

### 5. Review Process

- **Automated checks** must pass (CI/CD pipeline)
- **Code review** by maintainers
- **Address feedback** promptly and professionally
- **Rebase and squash** commits if requested

## Questions and Support

- **GitHub Issues** - For bugs and feature requests
- **GitHub Discussions** - For questions and general discussion
- **Documentation** - Check the wiki for detailed guides

Thank you for contributing to the Ansys MCP Server! 🚀