"""Deterministic PDF renderer for validated JSForm visual reports."""

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4, LEGAL, LETTER, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from JSForm.image_safety import validated_image_bytes


PAGE_SIZES = {"letter": LETTER, "legal": LEGAL, "a4": A4}


class ReportRenderError(RuntimeError):
    pass


class PDFReportRenderer:
    def render(self, definition, dataset, output, context=None):
        dataset.contract.validate_definition(definition)
        settings = definition.settings
        page_size = PAGE_SIZES[settings["pagesize"]]
        if settings["orientation"] == "landscape":
            page_size = landscape(page_size)
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        pdf = canvas.Canvas(str(target), pagesize=page_size, pageCompression=1)
        pdf.setTitle(definition.title)
        self._context = dict(context or {})
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
        self._page_number = page_number
        self._rendered_at = datetime.now()

        def start_page(first=False):
            nonlocal page_number
            self._page_number = page_number
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
            matrices = [(name, item) for name, item in band_controls if item["type"] == "matrix"]
            for _, table in tables:
                rows = self._sorted_rows(
                    dataset.collections[table["repeatcollection"]], definition,
                    dataset, table["repeatcollection"],
                )
                row_height = max(16, min(30, bands[band_name]["height"] / 2))
                header_height = row_height
                header_pending = True
                groups = self._groups_for(definition, table["repeatcollection"])
                active_values = None
                previous_row = None
                for row in rows:
                    changed = self._changed_group_index(groups, active_values, row)
                    forced_break = previous_row is not None and changed < len(groups) and any(
                        bands[item["headerband"]].get("pagebreakbefore")
                        or bands[item["footerband"]].get("pagebreakafter")
                        for item in groups[changed:]
                    )
                    group_header_height = sum(
                        bands[item["headerband"]]["height"] for item in groups[changed:]
                    )
                    required = row_height + group_header_height + (header_height if header_pending else 0)
                    if forced_break:
                        current_y = self._draw_group_footers(
                            pdf, definition, dataset, groups[changed:], previous_row,
                            table["repeatcollection"], current_y, margins,
                        )
                    if forced_break or current_y - required < usable_bottom + footer_height:
                        pdf.showPage()
                        page_number += 1
                        self._page_number = page_number
                        current_y = start_page(first=False)
                        header_pending = True
                        changed = 0
                    elif previous_row is not None and changed < len(groups):
                        current_y = self._draw_group_footers(
                            pdf, definition, dataset, groups[changed:], previous_row,
                            table["repeatcollection"], current_y, margins,
                        )
                    if header_pending:
                        current_y = self._draw_table_header(
                            pdf, table, current_y, margins["left"], header_height
                        )
                        header_pending = False
                    current_y = self._draw_group_headers(
                        pdf, definition, dataset, groups[changed:], row,
                        table["repeatcollection"], current_y, margins,
                    )
                    current_y = self._draw_table_row(
                        pdf, table, row, current_y, margins["left"], row_height
                    )
                    active_values = [row.get(item["field"]) for item in groups]
                    previous_row = row
                if previous_row is not None:
                    current_y = self._draw_group_footers(
                        pdf, definition, dataset, groups, previous_row,
                        table["repeatcollection"], current_y, margins,
                    )
                if not rows:
                    current_y = self._draw_empty_message(
                        pdf, definition, current_y, margins, page_width
                    )
            for _, matrix in matrices:
                rows = list(dataset.collections[matrix["repeatcollection"]])
                matrix_rows, column_values = self._matrix_values(matrix, rows)
                row_height, header_height = 20, 22
                header_pending = True
                for label, values, total in matrix_rows:
                    required = row_height + (header_height if header_pending else 0)
                    if current_y - required < usable_bottom + footer_height:
                        pdf.showPage()
                        page_number += 1
                        self._page_number = page_number
                        current_y = start_page(first=False)
                        header_pending = True
                    if header_pending:
                        current_y = self._draw_matrix_header(
                            pdf, matrix, column_values, current_y, margins["left"], header_height
                        )
                        header_pending = False
                    current_y = self._draw_matrix_row(
                        pdf, matrix, column_values, label, values, total,
                        current_y, margins["left"], row_height,
                    )
                if matrix_rows and matrix.get("showcolumntotals", True):
                    totals = [sum((row[1][index] for row in matrix_rows), Decimal(0))
                              for index in range(len(column_values))]
                    current_y = self._draw_matrix_row(
                        pdf, matrix, column_values, "Total", totals, sum(totals, Decimal(0)),
                        current_y, margins["left"], row_height, bold=True,
                    )
                if not matrix_rows:
                    current_y = self._draw_empty_message(
                        pdf, definition, current_y, margins, page_width
                    )
            for _, repeater in repeaters:
                rows = self._sorted_rows(
                    dataset.collections[repeater["repeatcollection"]], definition,
                    dataset, repeater["repeatcollection"],
                )
                groups = self._groups_for(definition, repeater["repeatcollection"])
                repeat_columns = repeater.get("repeatcolumns", 1)
                if repeat_columns > 1:
                    if groups:
                        raise ReportRenderError(
                            "Multi-column repeaters cannot also use report groups."
                        )
                    column_gap = repeater.get("columngap", 0)
                    column_width = repeater["size"][0]
                    for offset in range(0, len(rows), repeat_columns):
                        row_group = rows[offset:offset + repeat_columns]
                        height = max(self._repeater_height(repeater, row) for row in row_group)
                        if current_y - height <= usable_bottom + footer_height + 4:
                            pdf.showPage()
                            page_number += 1
                            self._page_number = page_number
                            current_y = start_page(first=False)
                        for column_index, row in enumerate(row_group):
                            column_left = margins["left"] + column_index * (
                                column_width + column_gap
                            )
                            self._draw_repeater(
                                pdf, repeater, row, current_y, column_left, height,
                            )
                        current_y -= height
                    if not rows:
                        current_y = self._draw_empty_message(
                            pdf, definition, current_y, margins, page_width
                        )
                    continue
                active_values = None
                previous_row = None
                for row in rows:
                    height = self._repeater_height(repeater, row)
                    changed = self._changed_group_index(groups, active_values, row)
                    forced_break = previous_row is not None and changed < len(groups) and any(
                        bands[item["headerband"]].get("pagebreakbefore")
                        or bands[item["footerband"]].get("pagebreakafter")
                        for item in groups[changed:]
                    )
                    group_header_height = sum(
                        bands[item["headerband"]]["height"] for item in groups[changed:]
                    )
                    if forced_break:
                        current_y = self._draw_group_footers(
                            pdf, definition, dataset, groups[changed:], previous_row,
                            repeater["repeatcollection"], current_y, margins,
                        )
                    if forced_break or current_y - height - group_header_height <= usable_bottom + footer_height + 4:
                        pdf.showPage()
                        page_number += 1
                        self._page_number = page_number
                        current_y = start_page(first=False)
                        changed = 0
                    elif previous_row is not None and changed < len(groups):
                        current_y = self._draw_group_footers(
                            pdf, definition, dataset, groups[changed:], previous_row,
                            repeater["repeatcollection"], current_y, margins,
                        )
                    current_y = self._draw_group_headers(
                        pdf, definition, dataset, groups[changed:], row,
                        repeater["repeatcollection"], current_y, margins,
                    )
                    self._draw_repeater(pdf, repeater, row, current_y, margins["left"], height)
                    current_y -= height
                    active_values = [row.get(item["field"]) for item in groups]
                    previous_row = row
                if previous_row is not None:
                    current_y = self._draw_group_footers(
                        pdf, definition, dataset, groups, previous_row,
                        repeater["repeatcollection"], current_y, margins,
                    )
                if not rows:
                    current_y = self._draw_empty_message(
                        pdf, definition, current_y, margins, page_width
                    )
        report_footer_height = sum(
            bands[name]["height"] for name in self._bands_of_type(bands, "reportfooter")
        )
        if report_footer_height:
            if current_y - report_footer_height <= usable_bottom + footer_height + 4:
                pdf.showPage()
                page_number += 1
                self._page_number = page_number
                current_y = start_page(first=False)
            self._draw_band_type(
                pdf, definition, dataset, "reportfooter", current_y, page_width, margins,
            )
        pdf.showPage()

    def _draw_empty_message(self, pdf, definition, top, margins, page_width):
        message = definition.settings.get("emptytext", "No records match the selected criteria.")
        pdf.setFont("Helvetica-Oblique", 10)
        pdf.setFillColorRGB(0.35, 0.35, 0.35)
        pdf.drawCentredString(page_width / 2, top - 20, message)
        return top - 36

    @staticmethod
    def _groups_for(definition, collection_name):
        return [
            item for item in definition.settings.get("groups", ())
            if item["collection"] == collection_name
        ]

    @staticmethod
    def _changed_group_index(groups, active_values, row):
        if active_values is None:
            return 0
        for index, item in enumerate(groups):
            if active_values[index] != row.get(item["field"]):
                return index
        return len(groups)

    def _draw_group_headers(
        self, pdf, definition, dataset, groups, row, collection_name, top, margins,
    ):
        for group in groups:
            top = self._draw_bound_band(
                pdf, definition, dataset, group["headerband"], row, collection_name,
                top, margins,
            )
        return top

    def _draw_group_footers(
        self, pdf, definition, dataset, groups, row, collection_name, top, margins,
    ):
        for group in reversed(groups):
            top = self._draw_bound_band(
                pdf, definition, dataset, group["footerband"], row, collection_name,
                top, margins,
            )
        return top

    def _draw_bound_band(
        self, pdf, definition, dataset, band_name, row, collection_name, top, margins,
    ):
        controls = self._controls_for_band(definition.controls, band_name)
        for _, control in controls:
            self._draw_control(
                pdf, control, dataset, margins["left"], top,
                current_row=row, current_collection=collection_name,
                definition=definition,
            )
        height = definition.bands[band_name]["height"]
        if definition.bands[band_name].get("autofit"):
            occupied = [
                control["position"][1] + control["size"][1]
                for _, control in controls
                if control.get("affectautofit", True)
                if self._control_has_content(control, dataset, row, collection_name)
            ]
            minimum = definition.bands[band_name].get("minimumheight", 24)
            height = min(height, max(minimum, max(occupied, default=20) + 4))
        return top - height

    @classmethod
    def _control_has_content(cls, control, dataset, row, collection_name):
        if control.get("visible", True) is False:
            return False
        if not cls._condition_matches(control.get("visiblewhen"), dataset, row, collection_name):
            return False
        if control["type"] in ("label", "line", "rectangle"):
            return bool(control.get("label")) or control["type"] in ("line", "rectangle")
        if control.get("collection") == collection_name and control.get("field"):
            return row.get(control["field"]) not in (None, "", b"")
        if control.get("collection") and control.get("field"):
            return cls._first_value(control, dataset) not in (None, "", b"")
        return True

    @classmethod
    def _sorted_rows(cls, rows, definition, dataset, collection_name):
        filters = [
            item for item in definition.settings.get("filters", ())
            if item["collection"] == collection_name
        ]
        result = [
            row for row in rows
            if all(cls._condition_matches(item, dataset, row, collection_name) for item in filters)
        ]
        specifications = [
            item for item in definition.settings.get("sort", ())
            if item["collection"] == collection_name
        ]
        collection = dataset.contract.collection(collection_name)
        for item in reversed(specifications):
            field = collection.field(item["field"])
            result.sort(
                key=lambda row, name=item["field"], kind=field.data_type:
                    cls._sort_value(row.get(name), kind),
                reverse=item["direction"] == "descending",
            )
        return result

    @staticmethod
    def _sort_value(value, data_type):
        if value is None or value == "":
            return (1, "")
        if data_type in ("integer", "decimal", "currency"):
            try:
                return (0, Decimal(str(value)))
            except (InvalidOperation, ValueError):
                return (0, Decimal(0))
        if data_type in ("date", "time", "datetime") and isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                pass
        if isinstance(value, (date, datetime, time)):
            return (0, value.isoformat())
        return (0, str(value).casefold())

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
                    self._draw_control(pdf, control, dataset, margins["left"], y, definition=definition)
            y -= height
        return y

    def _draw_footer(self, pdf, definition, dataset, bottom, page_width, margins, page_number):
        y = bottom + sum(
            definition.bands[name]["height"]
            for name in self._bands_of_type(definition.bands, "pagefooter")
        )
        for band_name in self._bands_of_type(definition.bands, "pagefooter"):
            for _, control in self._controls_for_band(definition.controls, band_name):
                self._draw_control(pdf, control, dataset, margins["left"], y, definition=definition)
            y -= definition.bands[band_name]["height"]
        has_page_control = any(
            control.get("type") == "systemtext" and control.get("systemvalue") == "page_number"
            for control in definition.controls.values()
        )
        if not has_page_control and definition.settings.get("showdefaultpagenumber", True):
            pdf.setFont("Helvetica", 8)
            pdf.setFillColorRGB(0.35, 0.35, 0.35)
            pdf.drawRightString(page_width - margins["right"], bottom + 6, f"Page {page_number}")

    def _draw_control(
        self, pdf, control, dataset, origin_x, band_top,
        current_row=None, current_collection=None, definition=None,
    ):
        if control.get("visible", True) is False:
            return
        if not self._condition_matches(control.get("visiblewhen"), dataset, current_row, current_collection):
            return
        x = origin_x + control["position"][0]
        width, height = control["size"]
        y = band_top - control["position"][1] - height
        kind = control["type"]
        if kind in {"label", "text", "systemtext", "aggregate"}:
            self._draw_background_and_border(pdf, control, x, y, width, height)
            if kind == "label":
                value = control.get("label", "")
            elif kind == "systemtext":
                value = self._system_value(control, definition)
            elif kind == "aggregate":
                value = self._aggregate_value(control, dataset, current_row, definition)
            else:
                value = self._bound_value(control, dataset, current_row, current_collection)
            self._draw_text(pdf, self._format_value(value, control.get("format", "text")), x, y, width, height, control)
        elif kind == "line":
            self._set_stroke(pdf, control)
            pdf.line(x, y + height / 2, x + width, y + height / 2)
        elif kind == "rectangle":
            background = control.get("background")
            if control.get("collection") and control.get("field"):
                background = self._bound_value(
                    control, dataset, current_row, current_collection
                )
                if not str(background or "").strip():
                    return
            self._set_stroke(pdf, control)
            fill = 0
            if background:
                pdf.setFillColorRGB(*self._hex_color(str(background), "#FFFFFF"))
                fill = 1
            pdf.rect(x, y, width, height, stroke=1, fill=fill)
        elif kind == "image":
            value = self._bound_value(control, dataset, current_row, current_collection)
            if value:
                try:
                    encoded, _metadata = validated_image_bytes(value)
                    pdf.drawImage(ImageReader(BytesIO(encoded)), x, y, width, height,
                                  preserveAspectRatio=True, anchor="c", mask="auto")
                except Exception:
                    raise ReportRenderError("Unable to render report image safely") from None

    def _system_value(self, control, definition):
        value_name = control["systemvalue"]
        values = {
            "run_date": f"{self._rendered_at.month}/{self._rendered_at.day}/{self._rendered_at.year}",
            "run_datetime": self._rendered_at,
            "run_user": self._context.get("run_user", ""),
            "page_number": self._page_number,
            "report_title": definition.title,
            "report_code": definition.report_id,
            "classification": definition.settings.get("classification", "official").replace("_", " ").title(),
        }
        value = values[value_name]
        return f"{control.get('prefix', '')}{value}"

    @classmethod
    def _condition_matches(cls, condition, dataset, current_row=None, current_collection=None):
        if not condition:
            return True
        if current_row is not None and condition["collection"] == current_collection:
            value = current_row.get(condition["field"])
        else:
            rows = dataset.collections[condition["collection"]]
            value = rows[0].get(condition["field"]) if rows else None
        operator = condition["operator"]
        if operator == "empty":
            return value in (None, "", (), [])
        if operator == "not_empty":
            return value not in (None, "", (), [])
        expected = condition.get("value")
        return value == expected if operator == "equals" else value != expected

    @staticmethod
    def _first_value(control, dataset):
        rows = dataset.collections[control["collection"]]
        return rows[0].get(control["field"]) if rows else ""

    @classmethod
    def _bound_value(cls, control, dataset, current_row=None, current_collection=None):
        if current_row is not None and control.get("collection") == current_collection:
            return current_row.get(control["field"], "")
        return cls._first_value(control, dataset)

    @staticmethod
    def _aggregate_value(control, dataset, current_row=None, definition=None):
        rows = list(dataset.collections[control["collection"]])
        if control["scope"] == "group" and current_row is not None and definition is not None:
            matching_groups = []
            for group in definition.settings.get("groups", ()):
                if group["collection"] != control["collection"]:
                    continue
                matching_groups.append(group)
                if group["name"] == control["group"]:
                    break
            rows = [
                row for row in rows
                if all(row.get(group["field"]) == current_row.get(group["field"])
                       for group in matching_groups)
            ]
        values = [row.get(control["field"]) for row in rows]
        if control["operation"] == "count":
            return len([value for value in values if value is not None and value != ""])
        numeric = []
        for value in values:
            if value is None or value == "":
                continue
            try:
                numeric.append(Decimal(str(value)))
            except (InvalidOperation, ValueError):
                continue
        if not numeric:
            return ""
        if control["operation"] == "sum":
            return sum(numeric, Decimal(0))
        if control["operation"] == "average":
            return sum(numeric, Decimal(0)) / len(numeric)
        if control["operation"] == "minimum":
            return min(numeric)
        if control["operation"] == "maximum":
            return max(numeric)
        return ""

    @staticmethod
    def _format_value(value, format_name="text"):
        if value is None:
            return ""
        if format_name == "boolean":
            return "Yes" if bool(value) else "No"
        if format_name in ("date", "time", "datetime"):
            parsed = value
            if isinstance(value, str):
                try:
                    parsed = datetime.fromisoformat(value)
                except ValueError:
                    return value
            if format_name == "date" and isinstance(parsed, (date, datetime)):
                return f"{parsed.month}/{parsed.day}/{parsed.year}"
            if format_name == "time" and isinstance(parsed, (time, datetime)):
                return parsed.strftime("%I:%M %p").lstrip("0")
            if format_name == "datetime" and isinstance(parsed, datetime):
                return f"{parsed.month}/{parsed.day}/{parsed.year} {parsed.strftime('%I:%M %p').lstrip('0')}"
            return str(value)
        if format_name in ("integer", "decimal", "currency"):
            try:
                number = Decimal(str(value))
            except (InvalidOperation, ValueError):
                return str(value)
            if format_name == "integer":
                return f"{number:,.0f}"
            if format_name == "currency":
                return f"${number:,.2f}"
            return f"{number:,.2f}"
        if format_name == "phone":
            digits = "".join(character for character in str(value) if character.isdigit())
            if len(digits) == 10:
                return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        return str(value)

    @staticmethod
    def _hex_color(value, default="#000000"):
        value = value or default
        return tuple(int(value[index:index + 2], 16) / 255 for index in (1, 3, 5))

    def _draw_text(self, pdf, value, x, y, width, height, style):
        family = style.get("font", "Helvetica")
        variants = {
            ("Helvetica", True, False): "Helvetica-Bold",
            ("Helvetica", False, True): "Helvetica-Oblique",
            ("Helvetica", True, True): "Helvetica-BoldOblique",
            ("Times-Roman", True, False): "Times-Bold",
            ("Times-Roman", False, True): "Times-Italic",
            ("Times-Roman", True, True): "Times-BoldItalic",
            ("Courier", True, False): "Courier-Bold",
            ("Courier", False, True): "Courier-Oblique",
            ("Courier", True, True): "Courier-BoldOblique",
        }
        family = variants.get((family, style.get("bold", False), style.get("italic", False)), family)
        size = style.get("fontsize", 10)
        lines = self._wrapped_lines(value, width, size)
        if len(lines) == 1:
            while size > 5 and stringWidth(lines[0], family, size) > width:
                size -= 0.5
        pdf.setFont(family, size)
        pdf.setFillColorRGB(*self._hex_color(style.get("color")))
        vertical = style.get("verticalalign", "middle")
        line_height = size + 2
        text_height = len(lines) * line_height
        if vertical == "top" or len(lines) > 1:
            baseline = y + max(1, height - size)
        elif vertical == "bottom":
            baseline = y + 1
        else:
            baseline = y + max(1, (height - size) / 2 + 1)
        align = style.get("align", "left")
        for index, line in enumerate(lines):
            line_baseline = baseline - index * line_height
            if line_baseline < y - 1:
                break
            if align == "right":
                pdf.drawRightString(x + width, line_baseline, line)
            elif align == "center":
                pdf.drawCentredString(x + width / 2, line_baseline, line)
            else:
                pdf.drawString(x, line_baseline, line)

    def _set_stroke(self, pdf, style):
        pdf.setStrokeColorRGB(*self._hex_color(style.get("bordercolor"), "#000000"))
        pdf.setLineWidth(style.get("borderwidth", 1))

    def _draw_background_and_border(self, pdf, style, x, y, width, height):
        fill = 0
        stroke = 0
        if style.get("background"):
            pdf.setFillColorRGB(*self._hex_color(style["background"], "#FFFFFF"))
            fill = 1
        if style.get("borderwidth", 0) > 0:
            self._set_stroke(pdf, style)
            stroke = 1
        if fill or stroke:
            pdf.rect(x, y, width, height, stroke=stroke, fill=fill)

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
        row_color = row.get(table.get("colorfield", ""), "#000000")
        for column in table["columns"]:
            value = self._format_value(row.get(column["field"], ""), column.get("format", "text"))
            self._draw_text(pdf, value, x + 4, top - height, column["width"] - 8, height,
                            {"font": "Helvetica", "fontsize": 9,
                             "align": column.get("align", "left"), "color": row_color})
            x += column["width"]
        return top - height

    @staticmethod
    def _matrix_values(matrix, rows):
        columns = sorted({row.get(matrix["columnfield"]) for row in rows}, key=lambda value: str(value))
        row_labels = sorted({row.get(matrix["rowfield"]) for row in rows}, key=lambda value: str(value))
        values = {}
        for row in rows:
            key = (row.get(matrix["rowfield"]), row.get(matrix["columnfield"]))
            try:
                amount = Decimal(str(row.get(matrix["valuefield"]) or 0))
            except (InvalidOperation, ValueError):
                amount = Decimal(0)
            values[key] = values.get(key, Decimal(0)) + amount
        matrix_rows = []
        for label in row_labels:
            amounts = [values.get((label, column), Decimal(0)) for column in columns]
            matrix_rows.append((label, amounts, sum(amounts, Decimal(0))))
        return matrix_rows, columns

    @staticmethod
    def _matrix_widths(matrix, column_count):
        row_width = matrix["rowwidth"]
        total_width = matrix["size"][0]
        total_column = 70 if matrix.get("showrowtotals", True) else 0
        value_width = (total_width - row_width - total_column) / max(1, column_count)
        return row_width, value_width, total_column

    def _draw_matrix_header(self, pdf, matrix, columns, top, left, height):
        x = left + matrix["position"][0]
        row_width, value_width, total_width = self._matrix_widths(matrix, len(columns))
        pdf.setFillColorRGB(0.90, 0.90, 0.90)
        pdf.rect(x, top - height, matrix["size"][0], height, fill=1, stroke=0)
        self._draw_text(pdf, matrix["rowlabel"], x + 4, top - height, row_width - 8, height,
                        {"fontsize": 8, "bold": True})
        x += row_width
        for column in columns:
            self._draw_text(pdf, str(column), x + 3, top - height, value_width - 6, height,
                            {"fontsize": 8, "bold": True, "align": "right"})
            x += value_width
        if total_width:
            self._draw_text(pdf, "Total", x + 3, top - height, total_width - 6, height,
                            {"fontsize": 8, "bold": True, "align": "right"})
        return top - height

    def _draw_matrix_row(self, pdf, matrix, columns, label, values, total, top, left, height, bold=False):
        x = left + matrix["position"][0]
        row_width, value_width, total_width = self._matrix_widths(matrix, len(columns))
        pdf.setStrokeColorRGB(0.82, 0.82, 0.82)
        pdf.setLineWidth(0.4)
        pdf.line(x, top - height, x + matrix["size"][0], top - height)
        self._draw_text(pdf, str(label), x + 4, top - height, row_width - 8, height,
                        {"fontsize": 8, "bold": bold})
        x += row_width
        format_name = matrix.get("format", "currency")
        for value in values:
            self._draw_text(pdf, self._format_value(value, format_name), x + 3, top - height,
                            value_width - 6, height, {"fontsize": 8, "bold": bold, "align": "right"})
            x += value_width
        if total_width:
            self._draw_text(pdf, self._format_value(total, format_name), x + 3, top - height,
                            total_width - 6, height, {"fontsize": 8, "bold": True, "align": "right"})
        return top - height

    @staticmethod
    def _wrapped_lines(value, width, font_size):
        result = []
        average = max(1, int(width / max(1, font_size * 0.52)))
        for paragraph in str(value or "").splitlines() or [""]:
            words = []
            for word in paragraph.split():
                if len(word) <= average:
                    words.append(word)
                else:
                    words.extend(
                        word[index:index + average]
                        for index in range(0, len(word), average)
                    )
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
        for item, lines, effective_y in self._repeater_layout(repeater, row):
            if item.get("type", "text") == "image":
                required = max(required, effective_y + item["size"][1] + 8)
                continue
            size = item.get("fontsize", 9)
            required = max(
                required,
                effective_y + max(item["size"][1], len(lines) * (size + 2)) + 8,
            )
        return required

    def _repeater_layout(self, repeater, row):
        placed = []
        result = []
        for item in sorted(repeater["items"], key=lambda value: value["position"][1]):
            if item.get("type", "text") == "image":
                x, original_y = item["position"]
                placed.append((x, item["size"][0], original_y + item["size"][1] + 2))
                result.append((item, [], original_y))
                continue
            size = item.get("fontsize", 9)
            value = self._format_value(row.get(item["field"], ""), item.get("format", "text"))
            lines = self._wrapped_lines(value, item["size"][0], size)
            x, original_y = item["position"]
            width = item["size"][0]
            effective_y = original_y
            for previous_x, previous_width, previous_bottom in placed:
                horizontal_overlap = x < previous_x + previous_width and previous_x < x + width
                if horizontal_overlap and effective_y < previous_bottom:
                    effective_y = previous_bottom
            rendered_height = max(item["size"][1], len(lines) * (size + 2))
            placed.append((x, width, effective_y + rendered_height + 2))
            result.append((item, lines, effective_y))
        return result

    def _draw_repeater(self, pdf, repeater, row, top, left, height):
        x0 = left + repeater["position"][0]
        if repeater.get("separator", True):
            pdf.setStrokeColorRGB(0.82, 0.82, 0.82)
            pdf.setLineWidth(0.4)
            pdf.line(x0, top - height, x0 + repeater["size"][0], top - height)
        for item, lines, effective_y in self._repeater_layout(repeater, row):
            x = x0 + item["position"][0]
            y_top = top - effective_y
            if item.get("type", "text") == "image":
                value = row.get(item["field"])
                if value:
                    try:
                        encoded, _metadata = validated_image_bytes(value)
                        pdf.drawImage(
                            ImageReader(BytesIO(encoded)), x, y_top - item["size"][1],
                            item["size"][0], item["size"][1], preserveAspectRatio=True,
                            anchor="c", mask="auto",
                        )
                    except Exception:
                        raise ReportRenderError(
                            "Unable to render repeating report image safely"
                        ) from None
                continue
            size = item.get("fontsize", 9)
            for index, line in enumerate(lines):
                line_style = dict(item)
                line_style["fontsize"] = size
                self._draw_text(
                    pdf, line, x, y_top - item["size"][1] - index * (size + 2),
                    item["size"][0], item["size"][1], line_style,
                )
