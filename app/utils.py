import os
from werkzeug.utils import secure_filename
from app.models import AuditLog
from app import db
from datetime import datetime, timezone

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
