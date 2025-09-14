from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="ansys-mcp-server",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Model Context Protocol server for Ansys simulation software",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/ansys-mcp-server",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Physics",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "ansys-mcp-server=ansys_mcp_server:main",
        ],
    },
    keywords="ansys, mcp, simulation, cfd, fea, engineering",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/ansys-mcp-server/issues",
        "Source": "https://github.com/yourusername/ansys-mcp-server",
        "Documentation": "https://github.com/yourusername/ansys-mcp-server/wiki",
    },
)