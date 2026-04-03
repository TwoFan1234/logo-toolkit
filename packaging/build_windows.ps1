$ErrorActionPreference = "Stop"
pip install -e .[dev]
pyinstaller packaging/logo_toolkit.spec
