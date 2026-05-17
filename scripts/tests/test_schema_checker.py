\
#!/usr/bin/env python3
# tests/test_schema_checker.py — stand-alone (no pytest required)

import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from schema_checker import extract_jsonld, validate_block, REQUIRED_FIELDS

HTML_WITH_LOCAL_BUSINESS = """\
<html><body>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"LocalBusiness","name":"Test Co","address":{"@type":"PostalAddress","streetAddress":"123 Main St","addressLocality":"Brisbane","addressRegion":"QLD","postalCode":"4000"}}
</script>
</body></html>"""


def test_extract_valid_block():
    blocks = extract_jsonld(HTML_WITH_LOCAL_BUSINESS)
    assert isinstance(blocks, list)
    assert len(blocks) >= 1, f"Expected >=1 block, got {len(blocks)}"


def test_validate_local_business_complete():
    block = {
        "@type": "LocalBusiness", "name": "Test Co",
        "@context": "https://schema.org",
        "address": {"@type": "PostalAddress", "streetAddress": "123 Main St"},
    }
    issues = validate_block(block, ["local-business"])
    assert isinstance(issues, list)
    assert len(issues) == 0, f"Expected no issues, got {issues}"


def test_validate_missing_address():
    block = {"@type": "LocalBusiness", "name": "Test Co"}
    issues = validate_block(block, ["local-business"])
    assert len(issues) >= 1
    assert any("address" in i.lower() for i in issues)


def test_validate_service_missing_name():
    block = {"@type": "Service", "provider": {"@type": "Organization", "name": "Foo"}}
    issues = validate_block(block, ["service"])
    assert len(issues) >= 1
    assert any("name" in i.lower() for i in issues)


def test_required_fields_completeness():
    assert "LocalBusiness" in REQUIRED_FIELDS
    assert "Service" in REQUIRED_FIELDS
    assert "Organization" in REQUIRED_FIELDS
    assert all("name" in v for k, v in REQUIRED_FIELDS.items() if k in ("LocalBusiness","Organization"))


def test_no_type_flags_missing_type():
    """Validator always flags missing @type, regardless of check list."""
    block = {"name": "Anything"}
    issues = validate_block(block, ["local-business"])
    assert isinstance(issues, list)
    assert len(issues) >= 1
    assert any("type" in i.lower() for i in issues)


if __name__ == "__main__":
    test_extract_valid_block();             print("OK  test_extract_valid_block")
    test_validate_local_business_complete(); print("OK  test_validate_local_business_complete")
    test_validate_missing_address();         print("OK  test_validate_missing_address")
    test_validate_service_missing_name();    print("OK  test_validate_service_missing_name")
    test_required_fields_completeness();     print("OK  test_required_fields_completeness")
    test_no_type_flags_missing_type();       print("OK  test_no_type_flags_missing_type")
    print("All passed.")
