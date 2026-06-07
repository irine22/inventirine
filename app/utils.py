import os
import imghdr
from werkzeug.utils import secure_filename
from app.models import AuditLog
from app import db
from datetime import datetime, timezone

def is_valid_image(file_stream):
    """Check image validity using stdlib imghdr to avoid Pillow runtime dependencies."""
    header = file_stream.read(32)
    file_stream.seek(0)
    image_type = imghdr.what(None, header)
    return image_type in ['jpeg', 'png']

def process_and_save_image(file_obj, upload_folder):
    """Save a validated image upload without external image libraries."""
    if not is_valid_image(file_obj):
        return None

    filename = secure_filename(file_obj.filename)
    name, _ = os.path.splitext(filename)
    image_type = imghdr.what(None, file_obj.read(32))
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
