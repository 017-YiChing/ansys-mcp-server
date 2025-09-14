# Ansys MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that provides AI assistants with the ability to interact with Ansys simulation software. This server enables seamless integration between AI tools and Ansys products like Fluent, MAPDL, Mechanical, and others.

## Features

- **Multi-Product Support**: Interface with various Ansys products (Fluent, MAPDL, Mechanical, Geometry)
- **Session Management**: Create and manage Ansys simulation sessions
- **File Operations**: Read and analyze Ansys files (.cas, .dat, .inp, .rst, etc.)
- **Command Execution**: Execute MAPDL commands and Fluent operations
- **Status Monitoring**: Check Ansys installation and module availability
- **Working Directory Management**: Organize simulation files and results

## Supported Ansys Products

- **Ansys Fluent** (via PyFluent)
- **Ansys MAPDL** (via PyMAPDL)
- **Ansys Mechanical** (via PyMechanical)
- **Ansys Geometry** (via PyAnsys Geometry)

## Installation

### Prerequisites

1. **Python 3.8+** is required
2. **Ansys Software** must be installed on your system
3. **Ansys Python Libraries** (PyAnsys packages) should be installed

### Install from PyPI (when available)

```bash
pip install ansys-mcp-server
```

### Install from Source

```bash
git clone https://github.com/yourusername/ansys-mcp-server.git
cd ansys-mcp-server
pip install -r requirements.txt
pip install -e .
```

### Install Ansys Python Packages

```bash
# Install PyAnsys packages based on your Ansys products
pip install ansys-fluent-core      # For Fluent
pip install ansys-mapdl-core       # For MAPDL
pip install ansys-mechanical-core  # For Mechanical
pip install ansys-geometry-core    # For Geometry
```

## Quick Start

### 1. Configuration

Set your Ansys installation path (optional):

```bash
export ANSYS_ROOT="/path/to/ansys/installation"
```

### 2. Running the Server

```bash
# Run as a standalone server
python ansys_mcp_server.py

# Or use the installed command
ansys-mcp-server
```

### 3. Integration with AI Tools

The server implements the MCP protocol and can be integrated with any MCP-compatible AI tool. Here's an example configuration:

```json
{
  "name": "ansys-mcp",
  "command": "python",
  "args": ["/path/to/ansys_mcp_server.py"],
  "env": {
    "ANSYS_ROOT": "/path/to/ansys"
  }
}
```

## Available Tools

### System Tools

- **check_ansys_status**: Verify Ansys installation and available modules
- **read_ansys_file**: Read and analyze various Ansys file formats

### Fluent Tools

- **create_fluent_session**: Launch a new Fluent session
- **run_fluent_commands**: Execute Fluent TUI commands

### MAPDL Tools

- **create_mapdl_session**: Launch a new MAPDL session
- **run_mapdl_commands**: Execute APDL commands

## Usage Examples

### Check Ansys Status

```python
# AI Assistant can use this tool to verify Ansys availability
result = await call_tool("check_ansys_status", {})
```

### Create a Fluent Session

```python
# Launch Fluent in 3D double precision mode
result = await call_tool("create_fluent_session", {
    "precision": "double",
    "dimension": "3d"
})
```

### Read an Ansys File

```python
# Analyze a Fluent case file
result = await call_tool("read_ansys_file", {
    "file_path": "/path/to/simulation.cas"
})
```

### Execute MAPDL Commands

```python
# Run MAPDL preprocessing commands
result = await call_tool("run_mapdl_commands", {
    "commands": [
        "/PREP7",
        "ET,1,SOLID186",
        "BLOCK,0,1,0,1,0,1",
        "ESIZE,0.1",
        "VMESH,ALL"
    ]
})
```

## Resources

The server provides access to:

- **ansys://status**: Real-time Ansys installation status
- **ansys://working-directory**: Current working directory and files
- **ansys://sessions**: Active Ansys sessions (future feature)

## Development

### Project Structure

```
ansys-mcp-server/
├── ansys_mcp_server.py    # Main server implementation
├── requirements.txt       # Dependencies
├── setup.py              # Package setup
├── README.md             # This file
├── LICENSE               # MIT License
├── tests/                # Test suite
│   ├── test_server.py
│   └── test_ansys_interface.py
└── examples/             # Usage examples
    ├── fluent_example.py
    └── mapdl_example.py
```

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black ansys_mcp_server.py
flake8 ansys_mcp_server.py
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Ansys](https://www.ansys.com/) for providing excellent simulation software
- [PyAnsys](https://github.com/ansys) project for Python interfaces
- [Model Context Protocol](https://modelcontextprotocol.io/) for the communication standard
- [Anthropic](https://www.anthropic.com/) for MCP development and support

## Support

- **Documentation**: [GitHub Wiki](https://github.com/yourusername/ansys-mcp-server/wiki)
- **Issues**: [GitHub Issues](https://github.com/yourusername/ansys-mcp-server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/ansys-mcp-server/discussions)

## Roadmap

- [ ] Support for more Ansys products (CFX, Icepak, etc.)
- [ ] Advanced file format support
- [ ] Real-time simulation monitoring
- [ ] Batch job management
- [ ] Cloud integration (Ansys Cloud, AWS, Azure)
- [ ] Advanced visualization tools
- [ ] Optimization workflow support
- [ ] Integration with Ansys Workbench

---

**Note**: This is an unofficial tool and is not affiliated with or endorsed by Ansys, Inc. Ansys is a registered trademark of Ansys, Inc.