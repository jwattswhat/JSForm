"""Ownership and safe shutdown of JSForm child windows."""

from collections.abc import MutableMapping


class ChildFormRegistry(MutableMapping):
    """Dictionary-compatible registry with idempotent child cleanup."""

    def __init__(self):
        self._forms = {}

    def __getitem__(self, key):
        return self._forms[key]

    def __setitem__(self, key, value):
        self._forms[key] = value

    def __delitem__(self, key):
        del self._forms[key]

    def __iter__(self):
        return iter(self._forms)

    def __len__(self):
        return len(self._forms)

    def register(self, name, child):
        self._forms[name] = child
        return child

    def unregister(self, name):
        return self._forms.pop(name, None)

    def close_all(self):
        """Detach first, then close every still-live native child window."""
        children = list(self._forms.values())
        self._forms.clear()
        for child in children:
            try:
                window = child.FORM
                if not window.IsBeingDeleted():
                    window.Close()
            except (AttributeError, RuntimeError):
                # A child may be partially constructed or already deleted by wx.
                continue

