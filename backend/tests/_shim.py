"""Test helper: make `app` and Member 1's `astronomy` importable; stub httpx only if it is not installed.

Member 1's package imports httpx at import time (it is in requirements.txt). The stub is used ONLY by
offline tests of pure-math functions and is never used in production.
"""
import os, sys, types

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)
try:
    import httpx  # noqa: F401
except ImportError:
    sys.modules["httpx"] = types.ModuleType("httpx")
