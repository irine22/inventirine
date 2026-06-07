import bleach
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileSize
from wtforms import StringField, FloatField, IntegerField, TextAreaField, SubmitField, BooleanField
from wtforms.validators import DataRequired, NumberRange

def sanitize_html(text):
    if text is None:
        return text
    return bleach.clean(text)

class ProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired()], filters=[sanitize_html])
    sku = StringField('SKU', validators=[DataRequired()], filters=[sanitize_html])
    category = StringField('Category', filters=[sanitize_html])
    unit_price = FloatField('Unit Price', validators=[DataRequired(), NumberRange(min=0.01)])
    quantity = IntegerField('Initial Stock Quantity', validators=[NumberRange(min=0)], default=0)
    reorder_threshold = IntegerField('Reorder Threshold', validators=[NumberRange(min=0)], default=10)
    is_available = BooleanField('Available for Ordering', default=True)
    image = FileField('Product Image', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Images only!')])
    description = TextAreaField('Description', filters=[sanitize_html])
    submit = SubmitField('Save Product')

class StockUpdateForm(FlaskForm):
    quantity_change = IntegerField('Stock Change (can be negative for reduction)', validators=[DataRequired()])
    notes = StringField('Notes (Optional)', filters=[sanitize_html])
    submit = SubmitField('Update Stock')

class OrderActionForm(FlaskForm):
    action = StringField('Action', validators=[DataRequired()]) # accept, reject
    destination = StringField('Destination', filters=[sanitize_html])
    delivery_date = StringField('Delivery Date', filters=[sanitize_html])
    note = StringField('Note (Optional)', filters=[sanitize_html])
    submit = SubmitField('Submit Action')

class ShipOrderForm(FlaskForm):
    tracking_number = StringField('Tracking Number', validators=[DataRequired()], filters=[sanitize_html])
    submit = SubmitField('Mark as Shipped')

class BulkImportForm(FlaskForm):
    file = FileField('Upload CSV/JSON', validators=[DataRequired(), FileAllowed(['csv', 'json'], 'CSV or JSON only!'), FileSize(max_size=5 * 1024 * 1024, message='File must be under 5MB')])
    submit = SubmitField('Import')
