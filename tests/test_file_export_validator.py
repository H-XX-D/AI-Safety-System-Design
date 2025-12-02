from pathlib import Path

from infrastructure.file_export_validator import FileExportValidator, ExportMethod


def _roots(tmp_path: Path) -> dict:
    roots = {'orchestrator': str(tmp_path / 'orchestrator')}
    for idx in range(1, 6):
        roots[f'research_{idx}'] = str(tmp_path / f'research_{idx}')
    for path in roots.values():
        Path(path).mkdir(parents=True, exist_ok=True)
    return roots


def test_validate_request_rejects_invalid_system(tmp_path):
    validator = FileExportValidator(
        export_base_dir=str(tmp_path / 'exports'),
        log_file=str(tmp_path / 'log.jsonl'),
        allowed_roots=_roots(tmp_path),
    )
    ok, msg, _ = validator.request_export(
        system_id='unknown_system',
        file_path='file.py',
        export_method=ExportMethod.USB_ENCRYPTED,
        requester_id='test',
        purpose='test')
    assert not ok
    assert 'Invalid export request' in msg


def test_validate_request_rejects_path_traversal(tmp_path):
    validator = FileExportValidator(
        export_base_dir=str(tmp_path / 'exports'),
        log_file=str(tmp_path / 'log.jsonl'),
        allowed_roots=_roots(tmp_path),
    )
    ok, msg, _ = validator.request_export(
        system_id='research_1',
        file_path='../etc/passwd',
        export_method=ExportMethod.AIR_GAPPED,
        requester_id='test',
        purpose='test')
    assert not ok


def test_validate_request_absolute_path_non_orchestrator(tmp_path):
    validator = FileExportValidator(
        export_base_dir=str(tmp_path / 'exports'),
        log_file=str(tmp_path / 'log.jsonl'),
        allowed_roots=_roots(tmp_path),
    )
    ok, msg, _ = validator.request_export(
        system_id='research_2',
        file_path='/etc/shadow',
        export_method=ExportMethod.SECURE_NETWORK,
        requester_id='test',
        purpose='test')
    assert not ok


def test_validate_request_absolute_path_orchestrator_allowed(tmp_path):
    roots = _roots(tmp_path)
    src = Path(roots['orchestrator']) / 'shadow.txt'
    src.write_text("secret")
    validator = FileExportValidator(
        export_base_dir=str(tmp_path / 'exports'),
        log_file=str(tmp_path / 'log.jsonl'),
        allowed_roots=roots,
    )
    ok, msg, record = validator.request_export(
        system_id='orchestrator',
        file_path=str(src),
        export_method=ExportMethod.SECURE_NETWORK,
        requester_id='test',
        purpose='test')
    # our fake implementation will create a placeholder; should succeed for orchestrator
    assert ok
    assert record is not None
