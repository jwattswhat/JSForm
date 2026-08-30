"""Bound untrusted image resources before JSForm invokes a full decoder."""

from __future__ import annotations

import io
import os
import stat
import warnings
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_WIDTH = 10_000
MAX_IMAGE_HEIGHT = 10_000
SUPPORTED_IMAGE_FORMATS = frozenset({"PNG", "JPEG", "BMP"})


class ImageValidationError(ValueError):
    """Raised when encoded image input cannot be decoded within safe limits."""


@dataclass(frozen=True)
class ImageMetadata:
    """Non-pixel metadata established by bounded image header inspection."""

    format: str
    width: int
    height: int
    encoded_bytes: int
    pixels: int


def effective_image_limit(value, default, ceiling, label):
    """Return a positive integral application limit clamped to a hard ceiling."""
    selected = default if value is None else value
    if isinstance(selected, bool) or not isinstance(selected, int) or selected <= 0:
        raise ImageValidationError(f"{label} must be a positive whole number.")
    return min(selected, ceiling)


def normalized_image_bytes(value) -> bytes:
    """Normalize supported bytes-like image input without accepting other objects."""
    if isinstance(value, bytes):
        return value
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    raise ImageValidationError("Image data must be binary.")


def validated_image_bytes(value, *, max_bytes=MAX_IMAGE_BYTES, max_pixels=MAX_IMAGE_PIXELS):
    """Return the immutable encoded snapshot and metadata validated together."""
    byte_limit = effective_image_limit(max_bytes, MAX_IMAGE_BYTES, MAX_IMAGE_BYTES, "Image byte limit")
    pixel_limit = effective_image_limit(
        max_pixels, MAX_IMAGE_PIXELS, MAX_IMAGE_PIXELS, "Image pixel limit",
    )
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise ImageValidationError("Image data must be binary.")
    if not value:
        raise ImageValidationError("The image is empty.")
    if len(value) > byte_limit:
        raise ImageValidationError("The encoded image is too large.")
    encoded = normalized_image_bytes(value)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(encoded)) as image:
                image_format = str(image.format or "").upper()
                if image_format not in SUPPORTED_IMAGE_FORMATS:
                    raise ImageValidationError("The image format is not supported.")
                width, height = image.size
                if (
                    isinstance(width, bool) or isinstance(height, bool)
                    or not isinstance(width, int) or not isinstance(height, int)
                    or width <= 0 or height <= 0
                ):
                    raise ImageValidationError("The image dimensions are invalid.")
                if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT:
                    raise ImageValidationError("The image dimensions are too large.")
                pixels = width * height
                if pixels > pixel_limit:
                    raise ImageValidationError("The image dimensions are too large.")
                if int(getattr(image, "n_frames", 1)) != 1:
                    raise ImageValidationError("Animated or multi-frame images are not supported.")
                image.verify()
    except ImageValidationError:
        raise
    except Exception:
        raise ImageValidationError("The image is unsupported or damaged.") from None
    return encoded, ImageMetadata(image_format, width, height, len(encoded), pixels)


def preflight_image(value, *, max_bytes=MAX_IMAGE_BYTES, max_pixels=MAX_IMAGE_PIXELS):
    """Inspect bounded encoded data and return metadata without loading pixels."""
    return validated_image_bytes(
        value, max_bytes=max_bytes, max_pixels=max_pixels,
    )[1]


def read_bounded_image(path, *, max_bytes=MAX_IMAGE_BYTES, max_pixels=MAX_IMAGE_PIXELS):
    """Read one regular local file through a hard byte bound and preflight it."""
    byte_limit = effective_image_limit(max_bytes, MAX_IMAGE_BYTES, MAX_IMAGE_BYTES, "Image byte limit")
    selected = Path(path)
    text = str(selected)
    if text.startswith(("\\\\", "//")):
        raise ImageValidationError("The image must be a regular local file.")
    try:
        with selected.open("rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ImageValidationError("The image must be a regular local file.")
            encoded = stream.read(byte_limit + 1)
    except ImageValidationError:
        raise
    except OSError:
        raise ImageValidationError("The image file could not be read.") from None
    if len(encoded) > byte_limit:
        raise ImageValidationError("The encoded image is too large.")
    encoded, metadata = validated_image_bytes(
        encoded, max_bytes=byte_limit, max_pixels=max_pixels,
    )
    return encoded, metadata
