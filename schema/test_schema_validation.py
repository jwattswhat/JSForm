
import os
import json
import pytest
from jsform.ui.form_ui import Form
from jsform.core.database import DatabaseConnection
from jsform.core.config import ConfigManager
from jsform.core.display import FontManager

class SchemaValidator:
    def __init__(self, schema_file):
        with open(schema_file, 'r') as f:
            self.schema = json.load(f)

    def validate(self, form_data):
        """Validate form data against the schema."""
        form_name = form_data.get("form_name")
        if form_name not in self.schema:
            raise ValueError(f"Form '{form_name}' is not defined in the schema.")
        
        form_schema = self.schema[form_name]
        for field in form_data["fields"]:
            self._validate_field(field, form_schema)

    def _validate_field(self, field, form_schema):
        """Validate individual fields for type, required status, etc."""
        field_name = field.get("field_name")
        field_type = field.get("type")
        
        if field_name not in form_schema["fields"]:
            raise ValueError(f"Field '{field_name}' is not defined in the schema.")
        
        expected_type = form_schema["fields"][field_name]["type"]
        if field_type != expected_type:
            raise ValueError(f"Field '{field_name}' has type mismatch. Expected '{expected_type}', got '{field_type}'.")

        required = form_schema["fields"][field_name].get("required", False)
        if required and not field.get("value"):
            raise ValueError(f"Field '{field_name}' is required but has no value.")

@pytest.mark.parametrize("form_file", [
    pytest.param(file, id=file) for file in os.listdir("forms/") if file.endswith(".json")
])
def test_form_schema_validation(form_file):
    # Load the schema
    schema_validator = SchemaValidator("jsform_schema.json")  # Load the renamed schema file

    # Set up environment
    db_connection = DatabaseConnection("user", "password", "localhost", "ChurchDB")
    config = ConfigManager(db_connection.connection, db_connection.connection)
    font_manager = FontManager()

    # Load the form from JSON
    form_path = os.path.join("forms", form_file)
    with open(form_path, 'r') as file:
        form_data = json.load(file)

    # Validate the form against the schema
    schema_validator.validate(form_data)

    # Load the form using the JSForm framework
    Form.load_from_json(form_path, db_connection, config, font_manager)

    print(f"Form '{form_file}' is valid according to the schema.")
