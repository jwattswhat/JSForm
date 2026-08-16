"""Small Windows Credential Manager adapter for application secrets."""

from __future__ import annotations

import ctypes
from ctypes import wintypes


CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168


class _Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


class WindowsCredentialStore:
    """Read and write generic secrets without placing them in configuration files."""

    def __init__(self):
        api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        pointer = ctypes.POINTER(_Credential)
        self._write = api.CredWriteW
        self._write.argtypes = [pointer, wintypes.DWORD]
        self._write.restype = wintypes.BOOL
        self._read = api.CredReadW
        self._read.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                               ctypes.POINTER(pointer)]
        self._read.restype = wintypes.BOOL
        self._delete = api.CredDeleteW
        self._delete.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self._delete.restype = wintypes.BOOL
        self._free = api.CredFree
        self._free.argtypes = [ctypes.c_void_p]

    @staticmethod
    def _target(target):
        value = str(target or "").strip()
        if not value:
            raise ValueError("Credential target is required.")
        return value

    def write(self, target, username, secret):
        """Store one secret under a stable application-specific target name."""
        target = self._target(target)
        encoded = str(secret or "").encode("utf-16-le")
        blob = (ctypes.c_ubyte * len(encoded)).from_buffer_copy(encoded)
        credential = _Credential()
        credential.Type = CRED_TYPE_GENERIC
        credential.TargetName = target
        credential.UserName = str(username or "")
        credential.CredentialBlobSize = len(encoded)
        credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
        credential.Persist = CRED_PERSIST_LOCAL_MACHINE
        if not self._write(ctypes.byref(credential), 0):
            raise ctypes.WinError(ctypes.get_last_error())

    def read(self, target):
        """Return ``(username, secret)`` or raise ``KeyError`` when absent."""
        target = self._target(target)
        pointer_type = ctypes.POINTER(_Credential)
        pointer = pointer_type()
        if not self._read(target, CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            error = ctypes.get_last_error()
            if error == ERROR_NOT_FOUND:
                raise KeyError("No credential is stored for this application setting.")
            raise ctypes.WinError(error)
        try:
            item = pointer.contents
            secret = ctypes.string_at(item.CredentialBlob, item.CredentialBlobSize).decode("utf-16-le")
            return item.UserName or "", secret
        finally:
            self._free(pointer)

    def exists(self, target):
        """Return whether a credential exists without returning its secret."""
        try:
            self.read(target)
            return True
        except KeyError:
            return False

    def delete(self, target):
        """Delete a credential and return ``False`` when it was already absent."""
        target = self._target(target)
        if self._delete(target, CRED_TYPE_GENERIC, 0):
            return True
        error = ctypes.get_last_error()
        if error == ERROR_NOT_FOUND:
            return False
        raise ctypes.WinError(error)
