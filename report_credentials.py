"""LimeReport-compatible password encoding for temporary report templates."""

import base64
import struct


_MASK = 0xFFFFFFFF
_ROUNDS = 12
_KEY = b"HjccbzHjlbyfCkjy"


def _rotl(value, count):
    count &= 31
    return ((value << count) | (value >> ((32 - count) & 31))) & _MASK


def _rotr(value, count):
    count &= 31
    return ((value >> count) | (value << ((32 - count) & 31))) & _MASK


def _schedule(key=_KEY):
    words = [0] * 4
    for index in range(16, 0, -1):
        slot = (index - 1) // 4
        words[slot] = ((words[slot] << 8) + key[index - 1]) & _MASK
    table = [0] * 26
    table[0] = 0xB7E15163
    for index in range(1, 26):
        table[index] = (table[index - 1] + 0x9E3779B9) & _MASK
    a = b = i = j = 0
    for _ in range(78):
        a = table[i] = _rotl((table[i] + a + b) & _MASK, 3)
        b = words[j] = _rotl((words[j] + a + b) & _MASK, a + b)
        i = (i + 1) % 26
        j = (j + 1) % 4
    return table


def encode_lime_password(password):
    """Return the Base64 Value attribute expected by LimeReport."""
    raw = str(password).encode("utf-8")
    if not raw:
        return ""
    table = _schedule()
    prior_a = prior_b = 0
    encrypted = bytearray()
    for offset in range(0, len(raw), 8):
        block = raw[offset:offset + 8].ljust(8, b"\0")
        plain_a, plain_b = struct.unpack("<II", block)
        a = (plain_a ^ prior_a) + table[0] & _MASK
        b = (plain_b ^ prior_b) + table[1] & _MASK
        for round_number in range(1, _ROUNDS + 1):
            a = (_rotl(a ^ b, b) + table[2 * round_number]) & _MASK
            b = (_rotl(b ^ a, a) + table[2 * round_number + 1]) & _MASK
        encrypted.extend(struct.pack("<II", a, b))
        prior_a, prior_b = plain_a, plain_b
    return base64.b64encode(encrypted).decode("ascii")


def decode_lime_password(encoded):
    """Decode a LimeReport password value; intended for compatibility tests."""
    raw = base64.b64decode(encoded)
    table = _schedule()
    prior_a = prior_b = 0
    decrypted = bytearray()
    for offset in range(0, len(raw), 8):
        a, b = struct.unpack("<II", raw[offset:offset + 8])
        for round_number in range(_ROUNDS, 0, -1):
            b = _rotr((b - table[2 * round_number + 1]) & _MASK, a) ^ a
            a = _rotr((a - table[2 * round_number]) & _MASK, b) ^ b
        plain_b = ((b - table[1]) & _MASK) ^ prior_b
        plain_a = ((a - table[0]) & _MASK) ^ prior_a
        decrypted.extend(struct.pack("<II", plain_a, plain_b))
        prior_a, prior_b = plain_a, plain_b
    return decrypted.rstrip(b"\0").decode("utf-8")
