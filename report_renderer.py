"""Deterministic PDF renderer for validated JSForm visual reports."""

from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4, LEGAL, LETTER, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


PAGE_SIZES = {"letter": LETTER, "legal": LEGAL, "a4": A4}


class ReportRenderError(RuntimeError):
    pass


class PDFReportRenderer:
    def render(self, definition, dataset, output):
        dataset.contract.validate_definition(definition)
        settings = definition.settings
        page_size = PAGE_SIZES[settings["pagesize"]]
        if settings["orientation"] == "landscape":
            page_size = landscape(page_size)
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        pdf = canvas.Canvas(str(target), pagesize=page_size, pageCompression=1)
        pdf.setTitle(definition.title)
        self._render_document(pdf, page_size, definition, dataset)
        pdf.save()
        return target

    def _render_document(self, pdf, page_size, definition, dataset):
        settings = definition.settings
        bands = settings["bands"]
        controls = definition.controls
        margins = settings["margins"]
        page_width, page_height = page_size
        usable_top = page_height - margins["top"]
        usable_bottom = margins["bottom"]
        footer_names = self._bands_of_type(bands, "pagefooter")
        footer_height = sum(bands[name]["height"] for name in footer_names)
        page_number = 1

        def start_page(first=False):
            nonlocal page_number
            y = usable_top
            if first:
                y = self._draw_band_type(pdf, definition, dataset, "reportheader", y, page_width, margins)
            y = self._draw_band_type(pdf, definition, dataset, "pageheader", y, page_width, margins)
            self._draw_footer(pdf, definition, dataset, usable_bottom, page_width, margins, page_number)
            return y

        current_y = start_page(first=True)
        detail_names = self._bands_of_type(bands, "detail")
        for band_name in detail_names:
            band_controls = self._controls_for_band(controls, band_name)
            tables = [(name, item) for name, item in band_controls if item["type"] == "table"]
            repeaters = [(name, item) for name, item in band_controls if item["type"] == "repeater"]
            for _, table in tables:
                rows = dataset.collections[table["repeatcollection"]]
                row_height = max(16, min(30, bands[band_name]["height"] / 2))
                header_height = row_height
                header_pending = True
                for row in rows:
                    required = row_height + (header_height if header_pending else 0)
                    if current_y - required < usable_bottom + footer_height:
                        pdf.showPage()
                        page_number += 1
                        current_y = start_page(first=False)
                        header_pending = True
                    if header_pending:
                        current_y = self._draw_table_header(
                            pdf, table, current_y, margins["left"], header_height
                        )
                        header_pending = False
                    current_y = self._draw_table_row(
                        pdf, table, row, current_y, margins["left"], row_height
                    )
            for _, repeater in repeaters:
                rows = dataset.collections[repeater["repeatcollection"]]
                for row in rows:
                    height = self._repeater_height(repeater, row)
                    if current_y - height < usable_bottom + footer_height:
                        pdf.showPage()
                        page_number += 1
                        current_y = start_page(first=False)
                    self._draw_repeater(pdf, repeater, row, current_y, margins["left"], height)
                    current_y -= height
        pdf.showPage()

    @staticmethod
    def _bands_of_type(bands, band_type):
        return [name for name, value in bands.items() if value["type"] == band_type]

    @staticmethod
    def _controls_for_band(controls, band_name):
        return [(name, control) for name, control in controls.items() if control["band"] == band_name]

    def _draw_band_type(self, pdf, definition, dataset, band_type, top, page_width, margins):
        y = top
        for band_name in self._bands_of_type(definition.bands, band_type):
            height = definition.bands[band_name]["height"]
            for _, control in self._controls_for_band(definition.controls, band_name):
                if control["type"] != "table":
                    self._draw_control(pdf, control, dataset, margins["left"], y)
            y -= height
        return y

    def _draw_footer(self, pdf, definition, dataset, bottom, page_width, margins, page_number):
        y = bottom + sum(
            definition.bands[name]["height"]
            for name in self._bands_of_type(definition.bands, "pagefooter")
        )
        for band_name in self._bands_of_type(definition.bands, "pagefooter"):
            for _, control in self._controls_for_band(definition.controls, band_name):
                self._draw_control(pdf, control, dataset, margins["left"], y)
            y -= definition.bands[band_name]["height"]
        pdf.setFont("Helvetica", 8)
        pdf.setFillColorRGB(0.35, 0.35, 0.35)
        pdf.drawRightString(page_width - margins["right"], bottom + 6, f"Page {page_number}")

    def _draw_control(self, pdf, control, dataset, origin_x, band_top):
        if control.get("visible", True) is False:
            return
        x = origin_x + control["position"][0]
        width, height = control["size"]
        y = band_top - control["position"][1] - height
        kind = control["type"]
        if kind in {"label", "text"}:
            value = control.get("label", "") if kind == "label" else self._first_value(control, dataset)
            self._draw_text(pdf, str(value or ""), x, y, width, height, control)
        elif kind == "line":
            self._set_stroke(pdf, control)
            pdf.line(x, y + height / 2, x + width, y + height / 2)
        elif kind == "rectangle":
            self._set_stroke(pdf, control)
            pdf.rect(x, y, width, height, stroke=1, fill=0)
        elif kind == "image":
            value = self._first_value(control, dataset)
            if value:
                try:
                    pdf.drawImage(ImageReader(BytesIO(bytes(value))), x, y, width, height,
                                  preserveAspectRatio=True, anchor="c", mask="auto")
                except Exception as error:
                    raise ReportRenderError("Unable to render report image") from error

    @staticmethod
    def _first_value(control, dataset):
        rows = dataset.collections[control["collection"]]
        return rows[0].get(control["field"]) if rows else ""

    @staticmethod
    def _hex_color(value, default="#000000"):
        value = value or default
        return tuple(int(value[index:index + 2], 16) / 255 for index in (1, 3, 5))

    def _draw_text(self, pdf, value, x, y, width, height, style):
        family = style.get("font", "Helvetica")
        if style.get("bold") and family == "Helvetica":
            family = "Helvetica-Bold"
        size = style.get("fontsize", 10)
        pdf.setFont(family, size)
        pdf.setFillColorRGB(*self._hex_color(style.get("color")))
        baseline = y + max(1, (height - size) / 2 + 1)
        align = style.get("align", "left")
        if align == "right":
            pdf.drawRightString(x + width, baseline, value)
        elif align == "center":
            pdf.drawCentredString(x + width / 2, baseline, value)
        else:
            pdf.drawString(x, baseline, value)

    def _set_stroke(self, pdf, style):
        pdf.setStrokeColorRGB(*self._hex_color(style.get("bordercolor"), "#000000"))
        pdf.setLineWidth(style.get("borderwidth", 1))

    def _draw_table_header(self, pdf, table, top, left, height):
        x = left + table["position"][0]
        pdf.setFillColorRGB(0.90, 0.90, 0.90)
        pdf.rect(x, top - height, sum(column["width"] for column in table["columns"]), height, fill=1, stroke=0)
        for column in table["columns"]:
            self._draw_text(pdf, column["label"], x + 4, top - height, column["width"] - 8, height,
                            {"font": "Helvetica", "fontsize": 9, "bold": True, "align": column.get("align", "left")})
            x += column["width"]
        return top - height

    def _draw_table_row(self, pdf, table, row, top, left, height):
        x = left + table["position"][0]
        total_width = sum(column["width"] for column in table["columns"])
        pdf.setStrokeColorRGB(0.82, 0.82, 0.82)
        pdf.setLineWidth(0.4)
        pdf.line(x, top - height, x + total_width, top - height)
        for column in table["columns"]:
            value = row.get(column["field"], "")
            self._draw_text(pdf, str(value or ""), x + 4, top - height, column["width"] - 8, height,
                            {"font": "Helvetica", "fontsize": 9, "align": column.get("align", "left")})
            x += column["width"]
        return top - height

    @staticmethod
    def _wrapped_lines(value, width, font_size):
        result = []
        average = max(1, int(width / max(1, font_size * 0.52)))
        for paragraph in str(value or "").splitlines() or [""]:
            words = paragraph.split()
            if not words:
                result.append("")
                continue
            line = words[0]
            for word in words[1:]:
                if len(line) + len(word) + 1 <= average:
                    line += " " + word
                else:
                    result.append(line)
                    line = word
            result.append(line)
        return result

    def _repeater_height(self, repeater, row):
        required = repeater["itemheight"]
        for item in repeater["items"]:
            size = item.get("fontsize", 9)
            lines = self._wrapped_lines(row.get(item["field"], ""), item["size"][0], size)
            required = max(required, item["position"][1] + max(item["size"][1], len(lines) * (size + 2)) + 8)
        return required

    def _draw_repeater(self, pdf, repeater, row, top, left, height):
        x0 = left + repeater["position"][0]
        pdf.setStrokeColorRGB(0.82, 0.82, 0.82)
        pdf.setLineWidth(0.4)
        pdf.line(x0, top - height, x0 + repeater["size"][0], top - height)
        for item in repeater["items"]:
            x = x0 + item["position"][0]
            y_top = top - item["position"][1]
            size = item.get("fontsize", 9)
            lines = self._wrapped_lines(row.get(item["field"], ""), item["size"][0], size)
            for index, line in enumerate(lines):
                line_style = dict(item)
                line_style["fontsize"] = size
                self._draw_text(
                    pdf, line, x, y_top - item["size"][1] - index * (size + 2),
                    item["size"][0], item["size"][1], line_style,
                )
