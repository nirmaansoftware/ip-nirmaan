"""``python -m nirmaan.mcp [--root .nirmaan]``: serve IP Nirmaan over MCP stdio."""

import argparse

from nirmaan.mcp import serve

parser = argparse.ArgumentParser(prog="python -m nirmaan.mcp", description=__doc__)
parser.add_argument("--root", default=".nirmaan", help="Where projects are stored.")
serve(parser.parse_args().root)
