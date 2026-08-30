"""Tests for bounded image inspection before JSForm decoder calls."""

from __future__ import annotations

import io
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from JSForm.image_safety import (
    MAX_IMAGE_BYTES,
    ImageValidationError,
    effective_image_limit,
    preflight_image,
    read_bounded_image,
    validated_image_bytes,
)


def encoded_image(image_format, *, size=(3, 2)):
    stream = io.BytesIO()
    Image.new("RGB", size, (40, 80, 120)).save(stream, format=image_format)
    return stream.getvalue()


def oversized_png_header(width=10_001, height=2):
    value = bytearray(encoded_image("PNG", size=(1, 1)))
    value[16:24] = struct.pack(">II", width, height)
    value[29:33] = struct.pack(">I", zlib.crc32(value[12:29]))
    return bytes(value)


class ImageSafetyTests(unittest.TestCase):
    def test_supported_static_formats_report_header_metadata(self):
        for requested, normalized in (("PNG", "PNG"), ("JPEG", "JPEG"), ("BMP", "BMP")):
            value = encoded_image(requested)
            with self.subTest(requested=requested):
                metadata = preflight_image(value)
                self.assertEqual(metadata.format, normalized)
                self.assertEqual((metadata.width, metadata.height), (3, 2))
                self.assertEqual(metadata.pixels, 6)
                self.assertEqual(metadata.encoded_bytes, len(value))

    def test_bytes_like_values_normalize_and_invalid_values_fail_safely(self):
        value = encoded_image("PNG")
        self.assertEqual(preflight_image(bytearray(value)).format, "PNG")
        self.assertEqual(preflight_image(memoryview(value)).format, "PNG")
        for invalid in (b"", b"not an image", "not bytes", value[:-12]):
            with self.subTest(invalid=type(invalid).__name__):
                with self.assertRaises(ImageValidationError):
                    preflight_image(invalid)

    def test_validated_snapshot_is_immutable_when_original_buffer_changes(self):
        original = bytearray(encoded_image("PNG"))
        encoded, metadata = validated_image_bytes(original)
        original[:] = b"x" * len(original)
        self.assertEqual(metadata.format, "PNG")
        self.assertNotEqual(encoded, bytes(original))
        self.assertEqual(preflight_image(encoded).format, "PNG")

    def test_unsupported_and_multiframe_images_are_rejected(self):
        gif = encoded_image("GIF")
        with self.assertRaisesRegex(ImageValidationError, "format"):
            preflight_image(gif)

        first = Image.new("RGB", (1, 1), "red")
        second = Image.new("RGB", (1, 1), "blue")
        stream = io.BytesIO()
        first.save(stream, format="PNG", save_all=True, append_images=[second])
        with self.assertRaisesRegex(ImageValidationError, "multi-frame"):
            preflight_image(stream.getvalue())

    def test_byte_dimension_and_pixel_limits_reject_before_pixel_loading(self):
        value = encoded_image("PNG", size=(4, 3))
        with self.assertRaisesRegex(ImageValidationError, "encoded"):
            preflight_image(value, max_bytes=len(value) - 1)
        with self.assertRaisesRegex(ImageValidationError, "dimensions"):
            preflight_image(value, max_pixels=11)
        oversized = oversized_png_header()
        with patch.object(Image.Image, "load", side_effect=AssertionError("pixels loaded")):
            with self.assertRaisesRegex(ImageValidationError, "dimensions"):
                preflight_image(oversized)

    def test_limits_reject_malformed_values_and_clamp_to_ceiling(self):
        for value in (True, 0, -1, 1.5, "5"):
            with self.subTest(value=value), self.assertRaises(ImageValidationError):
                effective_image_limit(value, 10, 20, "Limit")
        self.assertEqual(effective_image_limit(100, 10, 20, "Limit"), 20)

    def test_file_reader_uses_limit_plus_one_and_rejects_overflow(self):
        value = encoded_image("PNG")

        class TrackingStream(io.BytesIO):
            def __init__(self, content, descriptor):
                super().__init__(content)
                self.descriptor = descriptor
                self.requested = []

            def read(self, size=-1):
                self.requested.append(size)
                return super().read(size)

            def fileno(self):
                return self.descriptor

        with tempfile.TemporaryDirectory() as folder:
            regular = Path(folder) / "regular.bin"
            regular.write_bytes(b"x")
            with regular.open("rb") as descriptor_source:
                tracking = TrackingStream(value, descriptor_source.fileno())
                with patch("JSForm.image_safety.Path.open", return_value=tracking):
                    with self.assertRaisesRegex(ImageValidationError, "encoded"):
                        read_bounded_image(regular, max_bytes=len(value) - 1)
            self.assertEqual(tracking.requested, [len(value)])

    def test_database_rejection_is_cached_without_calling_wx_decoder(self):
        from JSForm.clsField import clsField

        picker = clsField.clsImagePickerCtrl
        events = []
        fake = SimpleNamespace(
            _value=None,
            _image_metadata=None,
            _as_bytes=picker._as_bytes,
            _limits=lambda: (1024, 100),
            _refresh_preview=lambda: events.append("refresh"),
        )
        value = oversized_png_header()
        picker.SetValue(fake, value)
        self.assertEqual(fake._value, value)
        self.assertIsNone(fake._image_metadata)
        self.assertEqual(events, ["refresh"])

        placeholders = []
        fake._show_placeholder = placeholders.append
        with patch("JSForm.clsField.wx.Image") as decoder:
            picker._refresh_preview(fake)
        decoder.assert_not_called()
        self.assertEqual(placeholders, ["Image unavailable"])

    def test_report_paths_reject_before_imagereader(self):
        from JSForm.report_renderer import PDFReportRenderer, ReportRenderError

        renderer = PDFReportRenderer()
        renderer._condition_matches = lambda *_args: True
        renderer._bound_value = lambda *_args: oversized_png_header()
        control = {
            "type": "image", "position": [0, 0], "size": [20, 20],
            "collection": "rows", "field": "Photo",
        }
        with patch("JSForm.report_renderer.ImageReader") as decoder:
            with self.assertRaisesRegex(ReportRenderError, "safely"):
                renderer._draw_control(object(), control, object(), 0, 100)
        decoder.assert_not_called()

        item = {"type": "image", "field": "Photo", "position": [0, 0], "size": [20, 20]}
        repeater = {"position": [0, 0], "size": [20, 20], "separator": False}
        renderer._repeater_layout = lambda *_args: [(item, [], 0)]
        with patch("JSForm.report_renderer.ImageReader") as decoder:
            with self.assertRaisesRegex(ReportRenderError, "safely"):
                renderer._draw_repeater(object(), repeater, {"Photo": oversized_png_header()}, 100, 0, 20)
        decoder.assert_not_called()

    def test_report_paths_accept_the_exact_validated_snapshot(self):
        from JSForm.report_renderer import PDFReportRenderer

        renderer = PDFReportRenderer()
        renderer._condition_matches = lambda *_args: True
        value = bytearray(encoded_image("PNG"))
        renderer._bound_value = lambda *_args: value
        control = {
            "type": "image", "position": [0, 0], "size": [20, 20],
            "collection": "rows", "field": "Photo",
        }
        sources = []
        pdf = SimpleNamespace(drawImage=lambda *_args, **_kwargs: None)

        def reader(source):
            sources.append(source.getvalue())
            return object()

        with patch("JSForm.report_renderer.ImageReader", side_effect=reader):
            renderer._draw_control(pdf, control, object(), 0, 100)

        item = {"type": "image", "field": "Photo", "position": [0, 0], "size": [20, 20]}
        repeater = {"position": [0, 0], "size": [20, 20], "separator": False}
        renderer._repeater_layout = lambda *_args: [(item, [], 0)]
        with patch("JSForm.report_renderer.ImageReader", side_effect=reader):
            renderer._draw_repeater(pdf, repeater, {"Photo": value}, 100, 0, 20)

        self.assertEqual(sources, [bytes(value), bytes(value)])

if __name__ == "__main__":
    unittest.main()
