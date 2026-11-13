"""Pytest configuration for Playblast Plus unit tests.

The tests/ directory is intentionally separate from the addon root so that
pytest can import lib/ modules without triggering the Blender addon
``__init__.py`` (which requires a running Blender instance).
"""
