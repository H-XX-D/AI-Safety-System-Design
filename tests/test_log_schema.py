from utilities.log_schema import validate_log_event, new_event, LogValidationError
from utilities.logging_config import log_event, get_logger


def test_validate_log_event_success():
    ev = new_event(event_type="audit_seed", component="audit", severity="INFO", message="seed", seed_hex="abc123")
    validate_log_event(ev)  # should not raise


def test_validate_log_event_missing_field():
    ev = {"event_type": "x"}  # missing others
    try:
        validate_log_event(ev)  # type: ignore[arg-type]
    except LogValidationError as e:
        assert "missing required" in str(e)
    else:
        raise AssertionError("Expected LogValidationError")


def test_log_event_wrapper_emits():
    logger = get_logger("test")
    # Just ensure no exception when logging a valid event
    log_event("test", event_type="integration", component="core", severity="INFO", message="ok", extra_details=5)
