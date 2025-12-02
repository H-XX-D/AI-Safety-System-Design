"""
File Export and Validation System
==================================

This module provides functionality to export files from any system in the AI safety
architecture and validate them against what's displayed on the interface.

Key Features:
1. Secure file export from research systems and orchestrator
2. Validation against interface display
3. Audit logging of all exports
4. Air-gapped or encrypted transfer options
5. Discrepancy detection and alerting
"""

import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
from enum import Enum
import logging

# Structured logger retrieval (allow external config)
logger = logging.getLogger("file_export_validator")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


class ExportMethod(Enum):
    """Methods for exporting files"""
    USB_ENCRYPTED = "usb_encrypted"
    AIR_GAPPED = "air_gapped"
    SECURE_NETWORK = "secure_network"


class ValidationResult(Enum):
    """Results of file validation"""
    MATCH = "match"
    MISMATCH = "mismatch"
    ERROR = "error"


@dataclass
class ExportRequest:
    """Request to export a file"""
    system_id: str  # e.g., "research_1", "orchestrator"
    file_path: str
    export_method: ExportMethod
    request_timestamp: str
    requester_id: str
    purpose: str


@dataclass
class ExportRecord:
    """Record of a file export"""
    request: ExportRequest
    export_timestamp: str
    file_hash: str
    export_location: str
    validation_result: Optional[ValidationResult]
    notes: str
    # Track airgap decodability (optional policy field)
    airgap_decodable: Optional[bool] = None
    airgap_reason: Optional[str] = None
    airgap_stats: Optional[Dict[str, int]] = None


@dataclass
class ValidationReport:
    """Report of validation between exported file and interface display"""
    export_record: ExportRecord
    interface_display_hash: str
    comparison_timestamp: str
    result: ValidationResult
    discrepancies: List[str]
    diff_excerpt: Optional[str] = None


class FileExportValidator:
    """
    Handles secure file exports and validation against interface display.

    This ensures transparency by allowing any file on any system to be exported
    and verified against what's shown on the interface.
    """

    def __init__(
        self,
        export_base_dir: str = "/var/ai_exports",
        log_file: str = "/var/log/ai_exports.jsonl",
        allowed_roots: Optional[Dict[str, str]] = None,
    ):
        self.export_base_dir = export_base_dir
        self.log_file = log_file
        self.allowed_roots = self._initialize_allowed_roots(allowed_roots)
        self._ensure_directories()

        # Lazy imports for decodability checks
        self._bitpacker = None
        self._aura = None

    def _initialize_allowed_roots(self, allowed_roots: Optional[Dict[str, str]]) -> Dict[str, str]:
        if allowed_roots is not None:
            return {k: os.path.abspath(v) for k, v in allowed_roots.items()}
        base = os.path.abspath(self.export_base_dir)
        roots = {f"research_{idx}": base for idx in range(1, 6)}
        roots["orchestrator"] = os.getcwd()
        return roots

    def _ensure_directories(self):
        """Ensure export directories exist"""
        try:
            os.makedirs(self.export_base_dir, exist_ok=True)
            # If log_file is in current directory (no dir component), use '.'
            log_dir = os.path.dirname(self.log_file) or '.'
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not ensure export directories: {e}")

    def request_export(self,
                      system_id: str,
                      file_path: str,
                      export_method: ExportMethod,
                      requester_id: str,
                      purpose: str) -> Tuple[bool, str, Optional[ExportRecord]]:
        """
        Request export of a file from a system.

        Returns (success, message, export_record)
        """
        request = ExportRequest(
            system_id=system_id,
            file_path=file_path,
            export_method=export_method,
            request_timestamp=datetime.now().isoformat(),
            requester_id=requester_id,
            purpose=purpose
        )

        # Validate request
        if not self._validate_request(request):
            return False, "Invalid export request", None

        # Perform export
        try:
            export_record = self._perform_export(request)
            # Policy: Immediately evaluate airgap decodability
            decodable, reason, stats = self.validate_airgap_decodability(export_record.export_location)
            export_record.airgap_decodable = decodable
            export_record.airgap_reason = reason
            export_record.airgap_stats = stats
            self._log_export(export_record)
            return True, f"File exported successfully to {export_record.export_location}", export_record
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return False, f"Export failed: {str(e)}", None

    def _validate_request(self, request: ExportRequest) -> bool:
        """Validate export request"""
        # Check if system_id is valid
        if request.system_id not in self.allowed_roots:
            return False
        # Basic path traversal / unsafe path checks
        if '..' in request.file_path.split(os.path.sep):
            return False
        return True

    def _safe_path_segment(self, value: str) -> str:
        """Sanitize a string so it can be used as a single path segment cross-platform."""
        return re.sub(r'[^A-Za-z0-9._-]', '_', value)

    def _perform_export(self, request: ExportRequest) -> ExportRecord:
        """Perform the actual file export"""
        source_path, placeholder_reason = self._resolve_source_path(request)
        # Create export directory
        folder_name = f"{self._safe_path_segment(request.system_id)}_{self._safe_path_segment(request.request_timestamp)}"
        export_dir = os.path.join(self.export_base_dir, folder_name)
        os.makedirs(export_dir, exist_ok=True)

        dest_file = os.path.join(export_dir, os.path.basename(request.file_path))

        if source_path and os.path.exists(source_path):
            shutil.copy2(source_path, dest_file)
            notes = "Export completed successfully"
        else:
            with open(dest_file, 'w') as f:
                f.write(f"Exported placeholder for {request.file_path} from {request.system_id}\n")
                f.write(f"Timestamp: {request.request_timestamp}\n")
                f.write(f"Purpose: {request.purpose}\n")
            notes = placeholder_reason or "Source file unavailable; placeholder generated"

        # Calculate hash
        file_hash = self._calculate_file_hash(dest_file)

        return ExportRecord(
            request=request,
            export_timestamp=datetime.now().isoformat(),
            file_hash=file_hash,
            export_location=dest_file,
            validation_result=None,
            notes=notes
        )

    def _resolve_source_path(self, request: ExportRequest) -> Tuple[Optional[str], Optional[str]]:
        """Resolve the source path for export, ensuring it lies within an allowed root."""
        base = self.allowed_roots.get(request.system_id)
        if not base:
            raise ValueError(f"No allowed root configured for system {request.system_id}")
        base = os.path.abspath(base)

        if os.path.isabs(request.file_path):
            candidate = os.path.abspath(request.file_path)
            if request.system_id != 'orchestrator':
                raise PermissionError("Absolute paths allowed only for orchestrator exports")
        else:
            candidate = os.path.abspath(os.path.join(base, request.file_path))

        if request.system_id != 'orchestrator' and not candidate.startswith(base):
            raise PermissionError("Requested file outside allowed export root")
        if request.system_id == 'orchestrator' and not candidate.startswith(base):
            # orchestrator can access absolute paths, but warn if outside allowed root
            return candidate, "orchestrator export outside configured root"
        return candidate, None

    # --- Airgap decodability policy ---
    def _lazy_init_decoders(self):
        """Initialize decoders on first use (avoid import cost if unused)."""
        if self._bitpacker is None:
            try:
                from communication.aura_bitpacked_extension import BitPackedCompressor
                self._bitpacker = BitPackedCompressor()
            except Exception as e:  # pragma: no cover
                logger.warning(f"BitPacked decoder unavailable: {e}")
                self._bitpacker = None
        if self._aura is None:
            try:
                # Use local wrapper to ensure ML selection is disabled
                from communication.aura_compressor import create_compressor
                self._aura = create_compressor(enable_aura=True)
            except Exception as e:  # pragma: no cover
                logger.warning(f"AURA decoder unavailable: {e}")
                self._aura = None

    def validate_airgap_decodability(self, file_path: str) -> Tuple[bool, str, Dict[str, int]]:
        """
        Check if a file is decodable by the airgapped hardware under the allowed formats:

        Allowed forms (in priority order):
        - Bit-Packed stream: concatenated 4-byte frames starting with method 0x06 and each frame decodes.
        - Single AURA message blob: decompressible by ProductionHybridCompressor.
        - Hex stream (lines): each hex line decodes to a valid Bit-Packed frame or AURA blob.

        Returns (is_decodable, reason, stats)
        stats keys: {frames_ok, frames_total}
        """
        self._lazy_init_decoders()

        stats: Dict[str, int] = {"frames_ok": 0, "frames_total": 0}

        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as e:
            return False, f"read_error: {e}", stats

        # Helper: try bitpacked stream
        def try_bitpacked_stream(buf: bytes) -> Tuple[bool, str]:
            if self._bitpacker is None:
                return False, "bitpacked_decoder_unavailable"
            # Allow secure frames (6 bytes) or standard frames (4 bytes)
            if len(buf) == 0:
                return False, "empty"
            if len(buf) % 4 == 0:
                frame_size = 4
            elif len(buf) % 6 == 0:
                frame_size = 6
            else:
                return False, "length_not_multiple_of_4_or_6"
            frames = len(buf) // frame_size
            ok = 0
            for i in range(frames):
                frame = buf[i*frame_size:(i+1)*frame_size]
                stats["frames_total"] += 1
                method_byte = frame[0]
                if method_byte == 0x06 and frame_size == 4:
                    if self._bitpacker.decompress(frame) is None:
                        return False, f"frame_{i}_undecodable"
                elif method_byte == 0x16 and frame_size == 6:
                    if self._bitpacker.decompress_secure(frame) is None:
                        return False, f"secure_frame_{i}_undecodable"
                else:
                    return False, f"frame_{i}_bad_method_byte:{method_byte:02x}"
                ok += 1
            stats["frames_ok"] += ok
            return True, "bitpacked_stream_ok" if frame_size == 4 else "bitpacked_secure_stream_ok"

        # Helper: try single AURA blob
        def try_aura_blob(buf: bytes) -> Tuple[bool, str]:
            if self._aura is None:
                return False, "aura_decoder_unavailable"
            try:
                _ = self._aura.decompress(buf)
                return True, "aura_single_ok"
            except Exception as e:
                return False, f"aura_error:{e}"

        # 1) Raw bitpacked stream
        ok, why = try_bitpacked_stream(data)
        if ok:
            return True, why, stats

        # 2) Single AURA blob
        ok, why = try_aura_blob(data)
        if ok:
            return True, why, stats

        # 3) Hex-stream lines
        try:
            text = None
            try:
                text = data.decode("utf-8")
            except Exception:
                text = None
            if text is not None and any(ch in text for ch in "\n\r"):
                lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                if lines:
                    all_ok = True
                    for i, ln in enumerate(lines):
                        try:
                            b = bytes.fromhex(ln)
                        except Exception:
                            all_ok = False
                            why = f"hex_line_{i}_invalid"
                            break
                        # Try bitpacked frame first
                        if len(b) == 4 and self._bitpacker is not None and b[0] == 0x06 and self._bitpacker.decompress(b) is not None:
                            stats["frames_total"] += 1
                            stats["frames_ok"] += 1
                            continue
                        if len(b) == 6 and self._bitpacker is not None and b[0] == 0x16 and self._bitpacker.decompress_secure(b) is not None:
                            stats["frames_total"] += 1
                            stats["frames_ok"] += 1
                            continue
                        # Try AURA blob line
                        ok_line, _ = try_aura_blob(b)
                        if not ok_line:
                            all_ok = False
                            why = f"line_{i}_undecodable"
                            break
                    if all_ok:
                        return True, "hex_stream_ok", stats
        except Exception as e:
            return False, f"hex_stream_error:{e}", stats

        return False, "no_known_decodable_format", stats

    def validate_against_interface(self,
                                 export_record: ExportRecord,
                                 interface_display_content: str,
                                 *,
                                 include_diff: bool = True,
                                 diff_context: int = 2) -> ValidationReport:
        """
        Validate exported file against what's displayed on the interface.

        Returns validation report
        """
        # Read exported file
        try:
            with open(export_record.export_location, 'r') as f:
                exported_content = f.read()
        except Exception as e:
            return ValidationReport(
                export_record=export_record,
                interface_display_hash="",
                comparison_timestamp=datetime.now().isoformat(),
                result=ValidationResult.ERROR,
                discrepancies=[f"Could not read exported file: {e}"]
            )

        # Calculate hashes
        exported_hash = hashlib.sha256(exported_content.encode()).hexdigest()
        interface_hash = hashlib.sha256(interface_display_content.encode()).hexdigest()

        # Compare
        if exported_hash == interface_hash:
            result = ValidationResult.MATCH
            discrepancies: List[str] = []
            diff_excerpt: Optional[str] = None
        else:
            result = ValidationResult.MISMATCH
            discrepancies = self._find_discrepancies(exported_content, interface_display_content)
            diff_excerpt = self._generate_diff_excerpt(exported_content, interface_display_content, context=diff_context) if include_diff else None

        # Update export record
        export_record.validation_result = result

        return ValidationReport(
            export_record=export_record,
            interface_display_hash=interface_hash,
            comparison_timestamp=datetime.now().isoformat(),
            result=result,
            discrepancies=discrepancies,
            diff_excerpt=diff_excerpt
        )

    def _find_discrepancies(self, content1: str, content2: str) -> List[str]:
        """Find discrepancies between two content strings"""
        discrepancies: List[str] = []

        lines1 = content1.split('\n')
        lines2 = content2.split('\n')

        max_lines = max(len(lines1), len(lines2))

        for i in range(max_lines):
            line1 = lines1[i] if i < len(lines1) else ""
            line2 = lines2[i] if i < len(lines2) else ""

            if line1 != line2:
                discrepancies.append(f"Line {i+1}: '{line1}' vs '{line2}'")

        return discrepancies

    def _generate_diff_excerpt(self, content1: str, content2: str, context: int = 2) -> str:
        """Generate a compact unified diff excerpt with limited context lines."""
        import difflib
        lines1 = content1.splitlines()
        lines2 = content2.splitlines()
        diff_lines = list(difflib.unified_diff(lines1, lines2, lineterm="", n=context))
        # Limit size to avoid huge reports
        if len(diff_lines) > 200:
            diff_lines = diff_lines[:200] + ["... (truncated)"]
        return "\n".join(diff_lines)

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def _log_export(self, export_record: ExportRecord):
        """Log export to audit file"""
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps({
                    'export_record': {
                        'system_id': export_record.request.system_id,
                        'file_path': export_record.request.file_path,
                        'export_method': export_record.request.export_method.value,
                        'request_timestamp': export_record.request.request_timestamp,
                        'requester_id': export_record.request.requester_id,
                        'purpose': export_record.request.purpose,
                        'export_timestamp': export_record.export_timestamp,
                        'file_hash': export_record.file_hash,
                        'export_location': export_record.export_location,
                        'validation_result': export_record.validation_result.value if export_record.validation_result else None,
                        'notes': export_record.notes,
                        'airgap_decodable': export_record.airgap_decodable,
                        'airgap_reason': export_record.airgap_reason,
                        'airgap_stats': export_record.airgap_stats
                    }
                }) + '\n')
        except Exception as e:
            logger.error(f"Failed to log export: {e}")


# Example usage
if __name__ == "__main__":
    # Initialize validator
    validator = FileExportValidator()

    # Request file export
    success, message, export_record = validator.request_export(
        system_id="research_1",
        file_path="alignment_filter.py",
        export_method=ExportMethod.USB_ENCRYPTED,
        requester_id="human_operator_123",
        purpose="Validate alignment filter implementation"
    )

    if success:
        print(f"Export successful: {message}")

        # Simulate interface display content
        interface_content = "def check_alignment():\n    return True\n"

        # Validate against interface
        assert export_record is not None
        report = validator.validate_against_interface(export_record, interface_content)

        print(f"Validation result: {report.result.value}")
        if report.discrepancies:
            print("Discrepancies found:")
            for disc in report.discrepancies:
                print(f"  {disc}")
    else:
        print(f"Export failed: {message}")
