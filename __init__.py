"""Public package exports for the JSForm desktop application framework."""

import types as _types

from JSForm.version import __version__
from JSForm.clsConstant import CONST
from JSForm.clsConfig import CONFIG
from JSForm.clsOption import OPTION
from JSForm.clsFont import FONT
from JSForm.clsLog import LG
from JSForm.clsMonitor import PMON

from JSForm.clsForm import clsForm
from JSForm.clsDB import clsDB, clsRecord
from JSForm.clsChoice import clsChoice
from JSForm.choice_manager import (
    ChoiceCatalogRepository, ChoiceManagerDialog, normalized_choices,
    show_choice_manager,
)
from JSForm.clsError import clsErrorHandler
from JSForm.clsSMTP import clsSMTP
from JSForm.clsSQL import clsSQL
from JSForm.clsField import clsField, getcontrolparameters
from JSForm.form_lifecycle import ChildFormRegistry
from JSForm.db_connections import DatabaseConnections, DatabaseSettings
from JSForm.record_state import OriginalRecord, RecordState
from JSForm.sql_statements import WriteStatements, quote_identifier
from JSForm.form_services import (
    ControlFactory, FormDefinitionError, FormDefinitionLoader, required_fields,
    resolve_form_schema,
)
from JSForm.report_definition import (
    ReportDefinition, ReportDefinitionError, ReportDefinitionLoader, ReportProtectionManifest,
    save_report_definition,
)
from JSForm.report_dataset import (
    ReportCollection, ReportDataset, ReportDatasetContract, ReportDatasetError,
    ReportField,
)
from JSForm.report_renderer import PDFReportRenderer, ReportRenderError
from JSForm.report_designer import (
    ReportCanvas, ReportDesignerFrame, ReportDesignerModel, open_report_designer,
)
from JSForm.report_catalog import ReportCatalogModel, open_report_catalog
from JSForm.screen_definition import (
    ScreenDefinition, ScreenDefinitionLoader, save_screen_definition,
    screen_definitions_equal,
)
from JSForm.screen_designer import (
    ScreenCanvas, ScreenDesignerFrame, ScreenDesignerModel, ScreenPreviewFrame,
    open_screen_designer, open_screen_preview,
)
from JSForm.screen_catalog import ScreenCatalogModel, open_screen_catalog
from JSForm.catalog_paths import CatalogDirectories, CatalogPathError
from JSForm.security import (
    AllowAllAuthorizationPolicy, AuthorizationDenied, DenyAllAuthorizationPolicy,
    FormSecurity,
)
from JSForm.layout_engine import (
    LayoutItem, apply_responsive_layout, build_layout_plan,
    frame_position, grouped_controls, layout_spacing, master_detail_orientation,
    master_detail_panes, supports_responsive_layout,
)
from JSForm.list_behavior import ListCtrlBehavior, ListSortState
from JSForm.grid_behavior import GridBehavior, grid_checked
from JSForm.ordered_children import (
    OrderedChildColumn, OrderedChildEditorDialog, OrderedChildModel,
)
from JSForm.search_select import (
    SearchSelectColumn, SearchSelectDialog, SearchSelectFilter, SearchSelectModel,
)
from JSForm.conditional_formatting import (
    ConditionalFormatter, STATUS_STYLES, StatusStyle, StatusSummaryCtrl,
    StatusSummaryItem, apply_conditional_controls, apply_control_style,
    condition_matches, status_style,
)
from JSForm.background_operation import (
    BackgroundOperationController, BackgroundOperationDialog, OperationResult,
    run_background_operation,
)
from JSForm.compact_dialogs import (
    CompactEditorDialog, CompactEditorModel, EditorField, LinkedRecordField,
    LinkedRecordViewerDialog, edit_compact_record, view_linked_record,
)
from JSForm.action_ui import (
    Action, OutputLocation, StandardActionBar, confirm_destructive_action,
    destructive_confirmation_message, install_action_menu,
)
from JSForm.error_reporting import (
    ErrorReporter, ErrorReportingConfig, configure_error_reporting, create_support_package,
    current_error_reporter, install_error_hooks, report_exception,
    restore_error_hooks,
)
from JSForm.error_dialog import show_error_dialog, show_error_dialog_threadsafe
from JSForm.control_values import phone_display, phone_storage
from JSForm.mail_service import (
    DeliveryResult, MailConfigurationError, MailDeliveryError, MailMessage,
    MailService, MailSettings, SMTPTransport, normalized_email,
    unique_recipients, valid_email,
)
from JSForm.credential_store import WindowsCredentialStore

from JSForm.fnUtil import convertNavButtons, charactertopoint, date_to_datetime, next_weekday, sql_table_exists, check_internetconnection
# Keep wildcard imports deterministic. The release test fingerprints this
# collection so an exported name cannot disappear unnoticed.
__all__ = tuple(
    name for name, value in globals().items()
    if (name == "__version__" or not name.startswith("_"))
    and not isinstance(value, _types.ModuleType)
)
