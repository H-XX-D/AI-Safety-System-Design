from pathlib import Path

from file_export_validator import FileExportValidator, ExportMethod


def _roots(tmp_path: Path) -> dict:
    roots = {'orchestrator': str(tmp_path / 'orchestrator')}
    for idx in range(1, 6):
        path = tmp_path / f'research_{idx}'
        path.mkdir(parents=True, exist_ok=True)
        roots[f'research_{idx}'] = str(path)
    return roots


def test_mismatch_diff_excerpt(tmp_path: Path):
    roots = _roots(tmp_path)
    source = Path(roots['research_1']) / 'dummy.txt'
    source.write_text("original\nLine2")
    validator = FileExportValidator(
        export_base_dir=str(tmp_path / 'exports'),
        log_file=str(tmp_path / 'log.jsonl'),
        allowed_roots=roots,
    )
    success, msg, record = validator.request_export(
        system_id='research_1',
        file_path='dummy.txt',
        export_method=ExportMethod.USB_ENCRYPTED,
        requester_id='tester',
        purpose='diff test'
    )
    assert success and record is not None
    interface_display = 'DIFFERENT CONTENT\nLine2'
    report = validator.validate_against_interface(record, interface_display, include_diff=True)
    if report.result.value == 'mismatch':
        assert report.diff_excerpt is not None
        assert '---' in report.diff_excerpt  # unified diff header
