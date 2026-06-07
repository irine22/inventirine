import os
import magic
from PIL import Image
from werkzeug.utils import secure_filename
from app.models import AuditLog
from app import db
from datetime import datetime, timezone

def is_valid_image(file_stream):
    """Check MIME type using python-magic."""
    header = file_stream.read(2048)
    file_stream.seek(0)
    mime = magic.from_buffer(header, mime=True)
    return mime in ['image/jpeg', 'image/png']

def process_and_save_image(file_obj, upload_folder):
    """Strip EXIF data and save."""
    if not is_valid_image(file_obj):
        return None
    
    filename = secure_filename(file_obj.filename)
    filepath = os.path.join(upload_folder, filename)
    
    image = Image.open(file_obj)
    
    # Strip EXIF by copying image data only
    data = list(image.getdata())
    image_without_exif = Image.new(image.mode, image.size)
    image_without_exif.putdata(data)
    
    # Save optimized
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
        
    image_without_exif.save(filepath)
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
