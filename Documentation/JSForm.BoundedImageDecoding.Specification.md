# JSForm bounded image decoding specification

Status: Approved and implemented

Approved by: Rev. Jonathan C. Watt

Verified: August 29, 2026 — 454 JSForm tests passed (2 skipped) and 1,063
ChurchManager tests passed (25 skipped).

Date: August 29, 2026

Framework owner: JSForm

Application owner: whether a field contains an image, application-specific
lower limits, user authorization to choose or remove an image, and the source
of report datasets

## 1. Purpose

JSForm shall reject oversized or decompression-amplifying image input before wx
or ReportLab performs a full pixel decode. The same framework policy shall cover
files chosen through `ImagePickerCtrl`, database BLOBs loaded into that control,
and database image values rendered into reports.

This specification addresses item 9 in the JSForm Codex Security remediation
queue: **Bound images before decoding.**

## 2. Current condition

`ImagePickerCtrl._choose_image()` checks the selected file's reported byte size,
then reads the entire file and constructs `wx.Image` before validating decoded
dimensions. A file can change between the size check and read, and a compact
image can demand excessive memory before the pixel limit is evaluated.

`ImagePickerCtrl.SetValue()` accepts database bytes without a byte or dimension
preflight. `_refresh_preview()` passes those bytes directly to `wx.Image`.

`PDFReportRenderer` passes bound image bytes directly to ReportLab
`ImageReader` in ordinary image and repeater-image paths. ReportLab may invoke
Pillow and decode the image before JSForm applies any resource limit.

## 3. Security invariants

1. No untrusted image bytes shall reach `wx.Image`, `wx.Bitmap`, ReportLab
   `ImageReader`, or another full decoder until the shared preflight accepts
   their encoded length, format, width, height, and total pixel count.
2. File input shall be read through a bounded operation that cannot allocate or
   retain more than the effective encoded-byte limit plus one detection byte.
3. A file changing after metadata inspection shall not bypass the final
   byte-length check.
4. Database-loaded values shall receive the same hard ceilings as selected
   files and report-bound values.
5. Application settings may lower limits but shall not raise or disable the
   framework hard ceilings.
6. Zero, negative, malformed, truncated, multi-frame, or unsupported images
   shall not reach a full decoder.
7. Rejected picker input shall not replace the control's previous value.
8. Rejected database BLOB input in `ImagePickerCtrl` shall remain byte-for-byte
   available from `GetValue()` but shall display a safe unavailable placeholder.
9. Rejected report images shall fail with fixed `ReportRenderError` guidance
   that contains no raw image data or parser exception text.

## 4. Shared image-safety service

A new application-neutral module shall own image preflight and bounded file
reading. Its public contract shall accept bytes-like values and return immutable
metadata containing the normalized format, width, height, encoded byte count,
and pixel count. It shall never return a Pillow image object or decoded pixel
buffer.

The service shall use Pillow only for lazy header inspection. It shall perform
no resize, color conversion, thumbnail generation, frame iteration, or pixel
loading. Pillow decompression-bomb warnings shall be treated as rejection, not
suppressed.

The same module shall expose a bounded file reader that opens a regular local
file, reads at most the effective byte limit plus one byte, rejects overflow,
and passes the resulting bytes through the shared preflight. It shall not use an
earlier `stat()` result as its security decision.

## 5. Supported images and limits

The framework shall accept the static formats already advertised by
`ImagePickerCtrl`: PNG, JPEG, and BMP. Animated or multi-frame content is outside
this control contract and shall be rejected even when its first frame resembles
a supported image.

Framework ceilings shall be:

- encoded bytes: 10 MiB;
- width: 10,000 pixels;
- height: 10,000 pixels; and
- total pixels: 20,000,000.

`ImagePickerCtrl` shall retain its existing `maxbytes` and `maxpixels` options.
Their defaults remain 5 MiB and 20,000,000 pixels. Positive application values
lower than the framework ceiling are honored; values above the ceiling are
clamped to it. Booleans, non-integral values, zero, and negative values are
invalid configuration and fail before image processing.

Width and height hard ceilings are not application-overridable. This prevents
extreme one-dimensional images even when total pixels remain within range.

## 6. Header validation

Preflight shall require all of the following before downstream decode:

1. a bytes, bytearray, or memoryview value;
2. a nonempty encoded value within the effective byte limit;
3. a Pillow-recognized PNG, JPEG, or BMP header;
4. positive integral width and height within the dimension ceilings;
5. a safely computed pixel count within the effective pixel limit;
6. exactly one frame; and
7. successful bounded structural verification after the size decision.

Any Pillow, parser, file, arithmetic, or format error shall become a fixed
framework image-validation error without raw exception text. Preflight shall
not trust filename extensions, MIME labels, database field names, or wx file
dialog wildcards as proof of image safety.

## 7. ImagePickerCtrl behavior

For a chosen file, JSForm shall obtain bytes and metadata only through the
bounded service. On rejection it shall show concise safe guidance and preserve
the current `_value` and preview. On acceptance it may assign the bytes and then
perform the existing scaled wx preview.

For `SetValue()` database input, JSForm shall preserve the original normalized
bytes first, then preflight them before preview. Accepted bytes may reach
`wx.Image`; rejected bytes shall never reach `wx.Image` and shall show
`Image unavailable`. `GetValue()` shall return the preserved bytes so an
unrelated record edit cannot silently save `NULL` or altered image data.

Resize events shall reuse the previous successful preflight state rather than
reinspect or decode rejected bytes. Existing aspect-ratio, no-upscale,
choose/remove, enable/disable, and placeholder behavior shall remain.

## 8. Report rendering

Both ordinary bound image controls and repeater image items shall call the same
preflight immediately before constructing `ImageReader`. The renderer may then
pass only accepted bytes to ReportLab.

Report definitions need no application-specific security property. The
framework hard ceilings apply uniformly. A rejected image shall abort the
report with `ReportRenderError("Unable to render report image safely")` or the
equivalent repeating-image message, preserving useful location context without
including parser details or bytes.

## 9. Compatibility

The following public behavior shall remain compatible:

- `ImagePickerCtrl` continues accepting bytes, bytearray, memoryview, or `None`;
- accepted PNG, JPEG, and BMP values round-trip as database bytes;
- the existing `maxbytes` and `maxpixels` JSON properties remain supported;
- chosen images are previewed and may be replaced or removed;
- invalid stored bytes remain preserved behind an unavailable placeholder;
- report `image` and repeater-image definitions retain their current JSON
  structure and rendering geometry; and
- current method names and application calls remain unchanged.

The intentional behavior change is that unsafe, unsupported, animated, or
over-ceiling images are never fully decoded. Application configurations can no
longer raise limits beyond framework ceilings.

## 10. Documentation

Implementation shall update both relevant JSON schemas if image-limit
properties are documented there, the framework and report references, public
API guidance, docstrings, samples as applicable, and the JSForm roadmap.
Documentation shall distinguish encoded byte size from decoded pixel cost.

## 11. Verification

Automated tests shall prove at minimum:

1. accepted PNG, JPEG, and BMP samples report correct metadata;
2. empty, malformed, truncated, unsupported, and multi-frame inputs fail safely;
3. encoded-byte, width, height, and pixel limits each reject at the boundary;
4. compressed images declaring excessive dimensions are rejected before a full
   decoder spy is called;
5. the bounded file reader reads no more than the limit plus one byte and does
   not rely on `stat()` for its final decision;
6. bytearray and memoryview inputs normalize safely;
7. malformed control limits and attempted above-ceiling limits fail or clamp as
   specified;
8. unsafe picker files preserve the previous value and preview;
9. unsafe database values remain byte-for-byte available while `wx.Image` is
   not called and the unavailable placeholder is shown;
10. accepted database values still preview with existing scale behavior;
11. ordinary and repeater report image paths reject before `ImageReader`;
12. accepted report images still reach `ImageReader` and retain geometry;
13. safe error messages contain neither raw parser details nor image bytes; and
14. the complete JSForm and ChurchManager suites remain compatible.

Fixtures shall be generated in memory from fictional images. Compressed-bomb
tests shall use crafted headers or metadata and shall never allocate the claimed
pixel buffer. New tests shall not load production database images.

## 12. Completion criteria

This item is complete when every framework image-decoding sink is routed through
the shared preflight; the implementation, schemas, documentation, and tests
satisfy this specification; full JSForm and ChurchManager verification passes;
and the roadmap records the verified result.

Automated tests may prove decode ordering with spies. No claim of visual image
quality or report-layout verification shall be made unless generated output is
separately rendered and inspected.
