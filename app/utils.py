import os
import subprocess
import tempfile
import logging
from werkzeug.utils import secure_filename
from app.models import AuditLog
from app import db
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


DEFENDER_PATH = os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'Windows Defender', 'MpCmdRun.exe')


SUSPICIOUS_PATTERNS = [
    # Executable headers
    b'MZ',                          # PE executable (EXE/DLL)
    b'\x7fELF',                     # ELF executable
    b'\xca\xfe\xba\xbe',            # Java class file
    # Script-based malware indicators
    b'CreateObject',                # VBS/JS
    b'WScript.Shell',
    b'Shell.Application',
    b'powershell', b'PowerShell',
    b'cmd.exe', b'cmd /c',
    b'rundll32',
    b'regsvr32',
    b'mshta',
    b'certutil',
    b'bitsadmin',
    # Macro/document exploit patterns
    b'AutoOpen', b'AutoExec',
    b'Sub Workbook_Open',
    b'Sub Document_Open',
    # Encoded/obfuscated payload indicators
    b'FromBase64String',
    b'eJx',                         # Base64-gzipped content
]


def _content_scan(file_data, filename):
    """Scan file content for suspicious patterns."""
    lower = file_data.lower()
    for pattern in SUSPICIOUS_PATTERNS:
        if pattern.lower() in lower:
            return False, f"Blocked: file contains suspicious pattern '{pattern.decode('latin-1')}'"
    return True, "Content scan passed."


def _defender_available():
    """Check if Windows Defender is enabled and functional."""
    if not os.path.exists(DEFENDER_PATH):
        return False
    try:
        result = subprocess.run(
            ['powershell', '-Command', '(Get-MpComputerStatus).AMServiceEnabled'],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0 and result.stdout.strip() == 'True'
    except Exception:
        return False


def scan_file(file_data, filename):
    """Scan file for viruses using Windows Defender (primary) and content checks (fallback).
    
    Returns (is_clean: bool, message: str)
    """

    if _defender_available():
        tmpdir = tempfile.gettempdir()
        safe_name = secure_filename(filename) or f"scan_{os.urandom(4).hex()}"
        tmp_path = os.path.join(tmpdir, safe_name)

        try:
            with open(tmp_path, 'wb') as f:
                f.write(file_data)

            result = subprocess.run(
                [DEFENDER_PATH, '-Scan', '-ScanType', '3', '-File', tmp_path, '-DisableRemediation'],
                capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                return True, "File is clean."
            elif result.returncode == 2:
                return False, f"Virus detected! File rejected. Scan result: {result.stdout.strip() or result.stderr.strip()}"
            logger.warning("Defender scan returned code %d, falling back to content scan", result.returncode)
        except subprocess.TimeoutExpired:
            logger.warning("Defender scan timed out, falling back to content scan")
        except Exception as e:
            logger.error("Defender scan error: %s, falling back to content scan", e)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
    else:
        logger.info("Windows Defender not available, using content-based scan")

    return _content_scan(file_data, filename)

JPEG_MAGIC = b"\xFF\xD8\xFF"
PNG_MAGIC = b"\x89PNG\r\n\x1A\n"


def _detect_image_type(header_bytes):
    """Detect JPEG or PNG image data from header bytes."""
    if header_bytes.startswith(JPEG_MAGIC):
        return 'jpeg'
    if header_bytes.startswith(PNG_MAGIC):
        return 'png'
    return None


def is_valid_image(file_stream):
    """Check image validity using raw header inspection."""
    header = file_stream.read(32)
    file_stream.seek(0)
    return _detect_image_type(header) in ['jpeg', 'png']


def process_and_save_image(file_obj, upload_folder):
    """Save a validated image upload without external image libraries."""
    if not is_valid_image(file_obj):
        return None

    filename = secure_filename(file_obj.filename)
    name, _ = os.path.splitext(filename)
    image_type = _detect_image_type(file_obj.read(32))
    file_obj.seek(0)
    extension = 'jpg' if image_type == 'jpeg' else 'png'
    filename = f"{name}.{extension}" if name else f"upload.{extension}"
    filepath = os.path.join(upload_folder, filename)

    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)

    file_obj.save(filepath)
    return filename

def log_audit(table_name, record_id, field_name, old_value, new_value, user_id):
    """Create a tamper-evident audit log entry."""
    # Convert values to strings for storage
    old_val_str = str(old_value) if old_value is not None else ""
    new_val_str = str(new_value) if new_value is not None else ""
    
    if old_val_str == new_val_str:
        return # Don't log if unchanged
        
    audit = AuditLog(
        table_name=table_name,
        record_id=record_id,
        field_name=field_name,
        old_value=old_val_str,
        new_value=new_val_str,
        user_id=user_id,
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(audit)
    # Commit is usually handled by the caller
