"""Approved-directory boundaries shared by JSForm customization catalogs."""

from __future__ import annotations

from pathlib import Path


class CatalogPathError(ValueError):
    pass


class CatalogDirectories:
    def __init__(self, user_directory, starter_directory, *, suffix=".json"):
        self.user = Path(user_directory).resolve()
        self.starters = Path(starter_directory).resolve()
        self.suffix = suffix.casefold()

    @staticmethod
    def _inside(path, root):
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def approved(self, path, *, must_exist=True):
        candidate = Path(path).resolve()
        if candidate.suffix.casefold() != self.suffix:
            raise CatalogPathError("Catalog files must use the {} extension.".format(self.suffix))
        if not (self._inside(candidate, self.user) or self._inside(candidate, self.starters)):
            raise CatalogPathError("The selected file is outside the approved catalog folders.")
        if must_exist and not candidate.is_file():
            raise CatalogPathError("The selected catalog file does not exist.")
        return candidate

    def user_target(self, filename):
        name = Path(filename)
        if name.name != str(filename) or name.suffix.casefold() != self.suffix:
            raise CatalogPathError("Enter a valid catalog filename.")
        return self.approved(self.user / name.name, must_exist=False)

    def user_file(self, path, *, must_exist=True):
        candidate = self.approved(path, must_exist=must_exist)
        if not self._inside(candidate, self.user):
            raise CatalogPathError("Only user customization files can be changed.")
        return candidate
