"""Entry point used by PyInstaller; normal users use the installed omvtool command."""

from omvtool.cli import main

raise SystemExit(main())
