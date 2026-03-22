import os
import json
import re
import pytest

METADATA_DIR = os.path.join(os.path.dirname(__file__), "..", "metadata")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# collect all metadata files
metadata_files = [f for f in os.listdir(METADATA_DIR) if f.endswith(".json")]

# .mark: modify test behavior, .parametrize: run the same test with different inputs
@pytest.mark.parametrize("filename", metadata_files)
def test_published_date_present_and_formatted(filename):
    """Each metadata file must have a non-empty published_date in YYYY-MM-DD format."""
    path = os.path.join(METADATA_DIR, filename)
    with open(path) as f:
        metadata = json.load(f)

    published_date = metadata.get("published_date")

    # check the field exists and isn't empty/null
    assert published_date, f"{filename}: published_date is missing or empty"

    # check it matches correct date format expected by supabase
    assert DATE_PATTERN.match(published_date), (
        f"{filename}: published_date '{published_date}' is not in YYYY-MM-DD format"
    )