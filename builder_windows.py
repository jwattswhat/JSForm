"""Shared startup behavior for JSForm visual Builder windows."""

from __future__ import annotations


def show_builder_window(window):
    """Maximize and show a Builder while preserving normal window controls."""
    window.Maximize(True)
    window.Show()
    return window
