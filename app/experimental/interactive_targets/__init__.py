"""Versioned interactive export target implementations.

Each subpackage is a restricted pure converter registered through
app/experimental/interactive_export_contract.py. Adapters own only their
in-memory file dictionaries: they never write external paths, install or launch
engines, fetch remote URLs or execute story code.
"""

__all__ = ['ink']
