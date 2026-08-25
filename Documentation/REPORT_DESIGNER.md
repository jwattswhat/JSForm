# JSForm Report Designer

The JSForm Report Designer is a native wxPython layout editor for validated
JSON report definitions. Applications provide an approved dataset contract and
the data used for previewing or rendering; report JSON never contains SQL,
database credentials, Python handlers, or permission logic.

## Report workflow

A complete report uses four application-neutral pieces:

1. `ReportDatasetContract` declares the collections and fields a report may use.
2. `ReportDefinitionLoader` validates the JSON layout.
3. `ReportDataset` carries immutable application-supplied rows.
4. `PDFReportRenderer` validates the definition against the contract and writes
   the finished PDF.

`ReportDesignerFrame` edits only the definition. The application remains
responsible for selecting records, querying its database, checking permissions,
building the dataset, choosing the output path, and opening or printing output.

## Define the approved data contract

```python
contract = JSForm.ReportDatasetContract(
    "sample.routemanifest",
    1,
    "sample.route_manifest",
    (
        JSForm.ReportCollection("route", "Route", (
            JSForm.ReportField("Route", "Route"),
            JSForm.ReportField("School", "School"),
        )),
        JSForm.ReportCollection("stops", "Stops", (
            JSForm.ReportField("Sequence", "Stop", "integer"),
            JSForm.ReportField("Time", "Time", "time"),
            JSForm.ReportField("StopName", "Location"),
        )),
    ),
)
```

The contract is an allow-list. A definition cannot bind to an unknown
collection or field. `required_permission` is application metadata; the
application must enforce that permission before opening, previewing, exporting,
or printing the report.

## Build immutable report data

Query application data outside JSForm and map it into the declared contract:

```python
dataset = JSForm.ReportDataset.create(contract, {
    "route": [{"Route": "North - AM", "School": "Pine Valley"}],
    "stops": [
        {"Sequence": 1, "Time": stop_time, "StopName": "Oak and First"},
    ],
})
```

Every declared collection must be supplied, even when it has no rows. Unknown
collections and row fields raise `ReportDatasetError`.

## Render a PDF

```python
definition = JSForm.ReportDefinitionLoader().load("Reports/SBRT01.json")
output = JSForm.PDFReportRenderer().render(
    definition,
    dataset,
    "Output/SBRT01.pdf",
    context={"requested_by": "Current user"},
)
```

Rendering validates the definition against the dataset contract before writing
the file. `ReportRenderError` represents bounded rendering failures.

## Open the visual designer

Keep shipped starters and user customizations in separate directories:

```python
from pathlib import Path
import shutil

starter = Path("Reports/SBRT01.json")
custom = Path(user_data_directory) / "Reports" / starter.name
custom.parent.mkdir(parents=True, exist_ok=True)
if not custom.exists():
    shutil.copy2(starter, custom)

frame = JSForm.open_report_designer(
    custom,
    dataset_contract=contract,
    preview_handler=lambda definition: JSForm.PDFReportRenderer().render(
        definition, dataset, Path(user_data_directory) / "Output" / "preview.pdf"
    ),
    starter_definition_path=starter,
    export_directory=Path(user_data_directory) / "Output",
)
```

`open_report_designer()` returns the modeless frame. If there is no running wx
main loop, it creates or uses a wx application and runs the loop until the
designer closes.

### Designer parameters

| Parameter | Purpose |
| --- | --- |
| `definition_path` | Editable JSON definition to open. |
| `dataset_contract` | Approved fields shown by the designer and used for validation. |
| `preview_handler` | Application callback that receives the current validated definition. |
| `starter_definition_path` | Protected definition used for comparison and restoration. |
| `export_directory` | Approved default folder for exported preview PDFs. |
| `protection_manifest` | Optional required settings, sections, and controls a customization cannot weaken. |

The designer must not be given a protected starter as its editable path. Copy
the starter to the user directory first or use the report catalog workflow.

## Designer interface

The designer provides:

- a report canvas with drag, resize, zoom, and optional snap-to-grid;
- report-control and report-section lists;
- approved dataset fields when a contract is supplied;
- property editing for geometry, text, formatting, colors, borders, visibility,
  and data binding;
- undo, redo, copy, paste, duplicate, delete, alignment, and distribution;
- page size, orientation, margins, sorting, grouping, totals, matrix controls,
  repeater items, table columns, and section-height editing;
- schema, dataset-contract, and protection-manifest validation;
- application-supplied PDF preview and export; and
- Save As, Restore Starter, Restore Previous, and Delete Customization recovery.

The **CUSTOMIZED** indicator compares the working report with its starter. A
dirty designer asks whether to save, discard, or cancel when closing.

`ReportDesignerModel` is the deterministic, undoable editing model behind the
window. Applications normally open `ReportDesignerFrame` through
`open_report_designer()` instead of manipulating the model directly.

## Report controls and sections

The report schema is authoritative. Common controls include labels, bound data,
system text, lines, rectangles, images, tables, repeaters, matrices, and
aggregates. Controls belong to named sections such as report header, page
header, detail, group header/footer, page footer, and report footer.

Definitions may also configure sorting, filters, grouping, page breaks,
multi-column repeaters, conditional visibility, default page numbers, and
repeater separators. Use the bundled
`schema/report_definition_schema.json`; do not copy parser behavior into an
application-specific schema.

## Catalog and customization lifecycle

`ReportCatalogModel` provides the safe folder-backed lifecycle used by
`open_report_catalog()` and its catalog dialog.

`open_report_catalog(user_directory, starters, open_handler, parent=None)`
opens the standard modal catalog. The catalog can:

- list protected starters and user-created reports;
- create a separate customization before opening the designer;
- create a new report from a selected definition;
- show whether the active definition is Starter or Customized; and
- delete a customization so the protected starter becomes active again.

The handler receives the editable customization path:

```python
def edit_report(path):
    JSForm.open_report_designer(
        path,
        dataset_contract=contract,
        starter_definition_path=Path("Reports") / path.name,
        export_directory=Path(user_data_directory) / "Output",
    )

JSForm.open_report_catalog(
    Path(user_data_directory) / "Reports",
    "Reports",
    edit_report,
    parent=main_frame,
)
```

Saving is atomic and retains the previous valid file as `<name>.json.bak`.
Restore operations load a starter or backup into working memory; the disk file
does not change until Save. Deleting a customization also removes its retained
backup and catalog marker.

## Protection manifest

Applications may require selected settings, sections, or controls:

```python
protection = JSForm.ReportProtectionManifest(
    required_bands=("Detail",),
    required_controls={
        "StudentName": {"collection": "students", "field": "Name"},
    },
    required_settings={"dataset": "school.students"},
)
```

Pass the manifest to `open_report_designer()`. It prevents a customization from
removing or weakening application-owned invariants, but it does not replace the
application's authorization checks.

## School Bus example

The complete sample is in
`examples/JSFormSample/route_manifest.py` with its starter definition at
`examples/JSFormSample/Reports/SBRT01.json`. It demonstrates contract
declaration, database-to-dataset mapping, PDF rendering, preview, starter
recovery, and user-local customization storage.

In the running sample, open **Tools > Designers > Report Designer**.

## Safety checklist

- Keep SQL and credentials out of report JSON.
- Authorize report design and report execution in the application.
- Keep starters read-only and user customizations separate.
- Supply only approved fields through a versioned dataset contract.
- Use a protection manifest for application-required report content.
- Write generated PDFs to an application-approved output directory.
- Validate before save, preview, export, or deployment.
- Treat rendered visual inspection separately from structural validation.
