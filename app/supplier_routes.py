import csv
import io
import json
import bleach
import os
import uuid
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.models import Product, InventoryMovement, Order, db
from app import limiter
from app.auth.routes import supplier_password_required
from app.utils import log_audit
from app.inventory.forms import ProductForm, StockUpdateForm, OrderActionForm, ShipOrderForm, BulkImportForm
from datetime import datetime, timezone

supplier_bp = Blueprint('supplier', __name__, url_prefix='/supplier')

def is_supplier(user):
    return user.is_authenticated and user.role == 'supplier'

@supplier_bp.before_request
def restrict_to_suppliers():
    if not is_supplier(current_user):
        flash('Access denied. Suppliers only.', 'danger')
        return redirect(url_for('inventory.dashboard'))

@supplier_bp.route('/products')
@login_required
def products():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    
    query = Product.query.filter_by(supplier_id=current_user.id, is_deleted=False)
    
    if search:
        query = query.filter(Product.name.ilike(f'%{search}%') | Product.sku.ilike(f'%{search}%'))
    if category:
        query = query.filter(Product.category.ilike(f'%{category}%'))
        
    products = query.all()
    
    categories = db.session.query(Product.category).filter_by(supplier_id=current_user.id, is_deleted=False).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template('supplier/products.html', products=products, categories=categories, search=search, active_cat=category)

@supplier_bp.route('/product/add', methods=['GET', 'POST'])
@login_required
def add_product():
    form = ProductForm()
    if form.validate_on_submit():
        image_path = None
        if form.image.data:
            file = form.image.data
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'products')
            os.makedirs(upload_path, exist_ok=True)
            file.save(os.path.join(upload_path, unique_filename))
            image_path = f'uploads/products/{unique_filename}'

        product = Product(
            name=form.name.data,
            sku=form.sku.data,
            category=form.category.data,
            unit_price=form.unit_price.data,
            quantity=form.quantity.data,
            reorder_threshold=form.reorder_threshold.data,
            description=form.description.data,
            is_available=form.is_available.data,
            image_path=image_path,
            supplier_id=current_user.id
        )
        db.session.add(product)
        db.session.commit()
        
        # Log audit
        log_audit('product', product.id, 'created', '', 'New product added', current_user.id)
        
        if product.quantity > 0:
            movement = InventoryMovement(
                product_id=product.id,
                movement_type='initial_stock',
                quantity_change=product.quantity,
                user_id=current_user.id,
                notes='Initial stock'
            )
            db.session.add(movement)
            db.session.commit()
            
        flash('Product added successfully.', 'success')
        return redirect(url_for('supplier.products'))
    elif request.method == 'POST':
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", 'danger')
                
    return render_template('supplier/product_form.html', form=form, title='Add Product')

@supplier_bp.route('/product/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    product = Product.query.filter_by(id=id, supplier_id=current_user.id, is_deleted=False).first_or_404()
    form = ProductForm(obj=product)
    
    if form.validate_on_submit():
        fields = ['name', 'sku', 'category', 'unit_price', 'reorder_threshold', 'description', 'is_available']
        for field in fields:
            old_val = getattr(product, field)
            new_val = getattr(form, field).data
            if old_val != new_val:
                log_audit('product', product.id, field, str(old_val), str(new_val), current_user.id)
                setattr(product, field, new_val)
        
        if form.image.data:
            file = form.image.data
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            upload_path = os.path.join(request.application.root_path, 'static', 'uploads', 'products')
            os.makedirs(upload_path, exist_ok=True)
            file.save(os.path.join(upload_path, unique_filename))
            product.image_path = f'uploads/products/{unique_filename}'
        
        # Quantity is handled separately via manual stock update
        db.session.commit()
        flash('Product updated successfully.', 'success')
        return redirect(url_for('supplier.products'))
    elif request.method == 'POST':
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", 'danger')
        
    return render_template('supplier/product_form.html', form=form, title='Edit Product', product=product)

@supplier_bp.route('/product/<int:id>/delete', methods=['POST'])
@login_required
def delete_product(id):
    product = Product.query.filter_by(id=id, supplier_id=current_user.id, is_deleted=False).first_or_404()
    
    pending_orders = Order.query.filter_by(product_id=product.id, status='pending').count()
    if pending_orders > 0:
        flash('Cannot delete product with pending orders.', 'danger')
        return redirect(url_for('supplier.products'))
        
    product.is_deleted = True
    log_audit('product', product.id, 'is_deleted', 'False', 'True', current_user.id)
    db.session.commit()
    flash('Product soft-deleted successfully.', 'success')
    return redirect(url_for('supplier.products'))

@supplier_bp.route('/product/<int:id>/stock', methods=['POST'])
@login_required
def update_stock(id):
    product = Product.query.filter_by(id=id, supplier_id=current_user.id, is_deleted=False).first_or_404()
    form = StockUpdateForm()
    if form.validate_on_submit():
        qty_change = form.quantity_change.data
        if product.quantity + qty_change < 0:
            flash('Cannot reduce stock below zero.', 'danger')
            return redirect(url_for('supplier.products'))
            
        old_qty = product.quantity
        product.quantity += qty_change
        
        log_audit('product', product.id, 'quantity', old_qty, product.quantity, current_user.id)
        
        movement = InventoryMovement(
            product_id=product.id,
            movement_type='adjustment',
            quantity_change=qty_change,
            user_id=current_user.id,
            notes=form.notes.data or 'Manual adjustment'
        )
        db.session.add(movement)
        db.session.commit()
        flash('Stock updated successfully.', 'success')
    return redirect(url_for('supplier.products'))

@supplier_bp.route('/movements')
@login_required
@supplier_password_required
def movements():
    movements = InventoryMovement.query.join(Product).filter(Product.supplier_id == current_user.id).order_by(InventoryMovement.timestamp.desc()).all()
    return render_template('supplier/movements.html', movements=movements)


@supplier_bp.route('/api/movements')
@login_required
@supplier_password_required
def api_movements():
    """JSON endpoint for real-time stock log polling."""
    from flask import jsonify
    since_id = request.args.get('since_id', 0, type=int)
    query = InventoryMovement.query.join(Product).filter(
        Product.supplier_id == current_user.id
    )
    if since_id > 0:
        query = query.filter(InventoryMovement.id > since_id)
    movements = query.order_by(InventoryMovement.timestamp.desc()).limit(100).all()
    data = []
    for mov in movements:
        data.append({
            'id': mov.id,
            'timestamp': mov.timestamp.strftime('%Y-%m-%d %H:%M:%S') if mov.timestamp else '',
            'product_name': mov.product.name,
            'product_sku': mov.product.sku,
            'movement_type': mov.movement_type,
            'quantity_change': mov.quantity_change,
            'user_id': mov.user_id,
            'notes': mov.notes or '',
        })
    return jsonify({'movements': data, 'count': len(data)})

@supplier_bp.route('/orders')
@login_required
@supplier_password_required
def orders():
    orders = Order.query.filter_by(supplier_id=current_user.id).order_by(Order.timestamp.desc()).all()
    return render_template('supplier/orders.html', orders=orders)

@supplier_bp.route('/api/orders/pending')
@login_required
@supplier_password_required
def api_pending_orders():
    # Return JSON of pending orders
    from flask import jsonify
    pending_orders = Order.query.filter_by(supplier_id=current_user.id, status='pending').order_by(Order.timestamp.desc()).all()
    data = []
    for order in pending_orders:
        data.append({
            'id': order.id,
            'product_name': order.product.name,
            'quantity': order.quantity,
            'status': order.status,
            'timestamp': order.timestamp.isoformat()
        })
    return jsonify({'count': len(data), 'orders': data})

@supplier_bp.route('/api/orders/all')
@login_required
@supplier_password_required
def api_all_orders():
    from flask import jsonify
    orders = Order.query.filter_by(supplier_id=current_user.id).order_by(Order.timestamp.desc()).all()
    data = []
    for order in orders:
        data.append({
            'id': order.id,
            'product_name': order.product.name,
            'quantity': order.quantity,
            'status': order.status,
            'timestamp': order.timestamp.strftime('%Y-%m-%d %H:%M'),
            'tracking_number': order.tracking_number,
            'destination': order.destination,
            'delivery_date': order.delivery_date.strftime('%Y-%m-%d') if order.delivery_date else None
        })
    return jsonify({'orders': data})

@supplier_bp.route('/order/<int:id>/action', methods=['POST'])
@login_required
@limiter.limit("30 per hour", override_defaults=True)
def order_action(id):
    order = Order.query.filter_by(id=id, supplier_id=current_user.id).first_or_404()
    form = OrderActionForm()
    if form.validate_on_submit():
        action = form.action.data
        if action == 'accept':
            if not form.destination.data or not form.delivery_date.data:
                flash('Destination and Delivery Date are required to accept an order.', 'danger')
                return redirect(url_for('supplier.orders'))
            order.status = 'processing'
            order.destination = form.destination.data
            try:
                order.delivery_date = datetime.strptime(form.delivery_date.data, '%Y-%m-%d').date()
            except ValueError:
                pass
                
            # Send message to admin
            from app.models import Message, User
            admin_user = User.query.filter_by(role='admin').first() or User.query.filter_by(email='bright12@gmail.com').first()
            if admin_user:
                msg = Message(
                    sender_id=current_user.id,
                    recipient_id=admin_user.id,
                    subject=f"Order Accepted: {order.product.name}",
                    body=f"Supplier {current_user.company_name or current_user.username} has accepted the order for {order.quantity}x {order.product.name}.\n\nShipping Date: {order.delivery_date}\nDestination: {order.destination}"
                )
                db.session.add(msg)
                
            flash('Order accepted for processing.', 'success')
        elif action == 'reject':
            order.status = 'rejected'
            # Assuming stock was reserved, we might free it. But IMS logic varies. 
            # If IMS deducted stock upon order creation, we must add it back:
            order.product.quantity += order.quantity
            log_audit('product', order.product.id, 'quantity', order.product.quantity - order.quantity, order.product.quantity, current_user.id)
            movement = InventoryMovement(
                product_id=order.product.id,
                movement_type='return',
                quantity_change=order.quantity,
                user_id=current_user.id,
                notes='Order rejected (dropped), stock freed'
            )
            db.session.add(movement)
            flash('Order dropped. An email has been sent to the admin.', 'warning')
            
            # Simulated email
            print(f"\n[EMAIL SENT] To: admin | Subject: Order Dropped | The supplier dropped order #{order.id} for product '{order.product.name}' due to unavailability.\n")
        
        order.note = form.note.data
        log_audit('order', order.id, 'status', 'pending', order.status, current_user.id)
        db.session.commit()
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {field}: {error}", 'danger')
    return redirect(url_for('supplier.orders'))

@supplier_bp.route('/order/<int:id>/ship', methods=['POST'])
@login_required
def order_ship(id):
    order = Order.query.filter_by(id=id, supplier_id=current_user.id).first_or_404()
    form = ShipOrderForm()
    if form.validate_on_submit():
        order.status = 'shipped'
        order.tracking_number = form.tracking_number.data
        log_audit('order', order.id, 'status', 'processing', 'shipped', current_user.id)
        db.session.commit()
        # Simulated notification
        flash(f'Order marked as shipped. Tracking: {order.tracking_number}', 'success')
    return redirect(url_for('supplier.orders'))


@supplier_bp.route('/product/<int:id>/finish', methods=['POST'])
@login_required
def finish_product(id):
    """Mark product as finished (set quantity to 0) for the current supplier."""
    product = Product.query.filter_by(id=id, supplier_id=current_user.id, is_deleted=False).first_or_404()
    if product.quantity == 0:
        flash('Product is already marked as finished.', 'info')
        return redirect(url_for('supplier.products'))

    old_qty = product.quantity
    product.quantity = 0
    log_audit('product', product.id, 'quantity', old_qty, 0, current_user.id)

    movement = InventoryMovement(
        product_id=product.id,
        movement_type='adjustment',
        quantity_change=-old_qty,
        user_id=current_user.id,
        notes='Marked as finished by supplier'
    )
    db.session.add(movement)
    db.session.commit()

    flash('Product marked as finished (quantity set to 0).', 'success')
    return redirect(url_for('supplier.products'))

@supplier_bp.route('/import', methods=['GET', 'POST'])
@login_required
def import_products():
    form = BulkImportForm()
    if form.validate_on_submit():
        file = form.file.data
        filename = file.filename
        content = file.read()
        
        errors = []
        success = 0
        
        if filename.endswith('.csv'):
            stream = io.StringIO(content.decode("UTF8"), newline=None)
            csv_input = csv.DictReader(stream)
            for i, row in enumerate(csv_input):
                try:
                    name = bleach.clean(row['name'])
                    sku = bleach.clean(row['sku'])
                    price = float(row['unit_price'])
                    if price <= 0: raise ValueError("Price must be > 0")
                    qty = int(row['quantity'])
                    if qty < 0: raise ValueError("Qty must be >= 0")
                    
                    product = Product(
                        name=name,
                        sku=sku,
                        category=bleach.clean(row.get('category', '')),
                        unit_price=price,
                        quantity=qty,
                        description=bleach.clean(row.get('description', '')),
                        supplier_id=current_user.id
                    )
                    db.session.add(product)
                    success += 1
                except Exception as e:
                    errors.append(f"Row {i+1}: {str(e)}")
        elif filename.endswith('.json'):
            try:
                data = json.loads(content.decode("UTF8"))
                for i, row in enumerate(data):
                    try:
                        name = bleach.clean(row['name'])
                        sku = bleach.clean(row['sku'])
                        price = float(row['unit_price'])
                        if price <= 0: raise ValueError("Price must be > 0")
                        qty = int(row['quantity'])
                        if qty < 0: raise ValueError("Qty must be >= 0")
                        
                        product = Product(
                            name=name,
                            sku=sku,
                            category=bleach.clean(row.get('category', '')),
                            unit_price=price,
                            quantity=qty,
                            description=bleach.clean(row.get('description', '')),
                            supplier_id=current_user.id
                        )
                        db.session.add(product)
                        success += 1
                    except Exception as e:
                        errors.append(f"Item {i+1}: {str(e)}")
            except Exception as e:
                errors.append(f"Invalid JSON format: {str(e)}")
                
        db.session.commit()
        if errors:
            flash(f"Imported {success} products with {len(errors)} errors. Check logs.", "warning")
            for err in errors[:5]: # show first 5
                flash(err, "danger")
        else:
            flash(f"Successfully imported {success} products.", "success")
        return redirect(url_for('supplier.products'))
    return render_template('supplier/import.html', form=form)
