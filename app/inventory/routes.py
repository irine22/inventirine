# pyrefly: ignore [missing-import]
from flask import Blueprint, render_template, redirect, url_for, request, flash
# pyrefly: ignore [missing-import]
from flask_login import login_required
from app import db, limiter
from app.auth.routes import admin_password_required
from sqlalchemy import func

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/')
@inventory_bp.route('/dashboard')
@login_required
def dashboard():
    from flask_login import current_user
    from app.models import Product, Supplier, Sale

    if current_user.role == 'supplier':
        return render_template('supplier_dashboard.html')
    elif current_user.role == 'user':
        return render_template('user_dashboard.html')

    products_count = Product.query.filter_by(is_deleted=False).count()
    low_stock_products = Product.query.filter(Product.quantity < 10, Product.is_deleted == False).all()
    suppliers_count = Supplier.query.count()
    
    # Calculate total sales value
    total_sales_value = sum(s.quantity_sold * s.sale_price for s in Sale.query.all())
    
    # Query categories and counts
    category_counts = db.session.query(Product.category, func.count(Product.id)).filter(Product.is_deleted == False).group_by(Product.category).all()
    categories = {cat: count for cat, count in category_counts if cat}
    
    # Query recent sales
    recent_sales = Sale.query.order_by(Sale.timestamp.desc()).limit(3).all()
    
    return render_template(
        'dashboard.html',
        products_count=products_count,
        low_stock_products=low_stock_products,
        suppliers_count=suppliers_count,
        total_sales_value=total_sales_value,
        categories=categories,
        recent_sales=recent_sales
    )

@inventory_bp.route('/order-stock', methods=['GET', 'POST'])
@login_required
@limiter.limit("30 per hour")
def order_stock():
    from app.models import Product, User, ActivityLog
    products = Product.query.filter_by(is_deleted=False, is_available=True).all()
    suppliers = User.query.filter_by(role='supplier', is_deleted=False).all()
    
    if request.method == 'POST':
        product_id = request.form.get('product_id')
        supplier_id = request.form.get('supplier_id')
        qty = request.form.get('quantity')
        
        if not product_id or not supplier_id or not qty:
            flash('Please select a supplier, a product, and enter a valid quantity.', 'danger')
            return redirect(url_for('inventory.order_stock'))
        
        try:
            qty = int(qty)
            if qty <= 0:
                flash('Quantity must be greater than zero.', 'danger')
                return redirect(url_for('inventory.order_stock'))
        except ValueError:
            flash('Invalid quantity entered.', 'danger')
            return redirect(url_for('inventory.order_stock'))
            
        product = Product.query.get(product_id)
        if not product:
            flash('Selected product does not exist.', 'danger')
            return redirect(url_for('inventory.order_stock'))

        # Use the supplier chosen by the admin
        supplier = User.query.filter_by(id=int(supplier_id), role='supplier', is_deleted=False).first()
        if not supplier:
            flash('The selected supplier is unavailable.', 'danger')
            return redirect(url_for('inventory.order_stock'))
            
        # Create an Order for the chosen supplier
        from app.models import Order
        from flask_login import current_user
        
        order = Order(
            product_id=product.id,
            supplier_id=supplier.id,
            quantity=qty,
            status='pending',
            note='Admin requested stock'
        )
        db.session.add(order)
        
        # Log to ActivityLog
        log = ActivityLog(user_id=current_user.id, action=f"Placed order for {qty} units of product {product.name} to supplier {supplier.company_name or supplier.username} ({supplier.email})")
        db.session.add(log)
        db.session.commit()
        
        flash(f'Success! Order placed for {qty} units of {product.name} → sent to {supplier.company_name or supplier.username} ({supplier.email}). Awaiting supplier confirmation.', 'success')
        return redirect(url_for('inventory.dashboard'))
        
    return render_template('inventory/order_stock.html', products=products, suppliers=suppliers)

@inventory_bp.route('/admin/orders')
@login_required
def admin_orders():
    from app.models import Order
    orders = Order.query.order_by(Order.timestamp.desc()).all()
    return render_template('inventory/admin_orders.html', orders=orders)

@inventory_bp.route('/api/admin/orders')
@login_required
def api_admin_orders():
    from app.models import Order, User
    from flask import jsonify
    orders = Order.query.order_by(Order.timestamp.desc()).all()
    data = []
    for order in orders:
        supplier = User.query.get(order.supplier_id)
        data.append({
            'id': order.id,
            'product_name': order.product.name,
            'quantity': order.quantity,
            'status': order.status,
            'supplier_name': supplier.username if supplier else 'Unknown',
            'tracking_number': order.tracking_number or '-',
            'timestamp': order.timestamp.strftime('%Y-%m-%d %H:%M')
        })
    return jsonify({'orders': data, 'count': len(data)})

@inventory_bp.route('/admin/dashboard')
@admin_password_required
def admin_dashboard_redirect():
    return redirect(url_for('inventory.dashboard'))

@inventory_bp.route('/profile')
@inventory_bp.route('/user/profile')
@login_required
def profile_redirect():
    return redirect(url_for('auth.profile'))

@inventory_bp.route('/admin/database')
@admin_password_required
def admin_db():
    from app.models import User, Product, Supplier, Sale, InventoryMovement
    users = User.query.all()
    products = Product.query.all()
    suppliers = Supplier.query.all()
    sales = Sale.query.all()
    movements = InventoryMovement.query.all()
    return render_template('admin_db.html', users=users, products=products, 
                           suppliers=suppliers, sales=sales, movements=movements)

@inventory_bp.route('/admin/product/<int:id>/edit', methods=['GET', 'POST'])
@admin_password_required
@limiter.limit("30 per hour", override_defaults=True)
def edit_product(id):
    import bleach
    from app.models import Product
    from flask_login import current_user
    product = Product.query.get_or_404(id)
    
    if request.method == 'POST':
        # Validate and sanitize all inputs
        errors = []

        name = request.form.get('name', '').strip()
        sku = request.form.get('sku', '').strip()
        unit_price_str = request.form.get('unit_price', '').strip()
        quantity_str = request.form.get('quantity', '').strip()
        location = request.form.get('location', '').strip()

        if not name:
            errors.append('Product name is required.')
        if not sku:
            errors.append('SKU is required.')

        try:
            unit_price = float(unit_price_str)
            if unit_price <= 0:
                errors.append('Price must be greater than zero.')
        except (ValueError, TypeError):
            errors.append('Invalid price format.')

        try:
            quantity = int(quantity_str)
            if quantity < 0:
                errors.append('Quantity cannot be negative.')
        except (ValueError, TypeError):
            errors.append('Invalid quantity format.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('inventory/edit_product.html', product=product)

        product.name = bleach.clean(name)
        product.sku = bleach.clean(sku)
        product.unit_price = unit_price
        product.quantity = quantity
        product.location = bleach.clean(location) if location else product.location

        from app.models import ActivityLog
        log = ActivityLog(user_id=current_user.id, action=f"Updated product {product.name} (SKU: {product.sku})")
        db.session.add(log)
        db.session.commit()
        flash(f'Product {product.name} updated successfully.', 'success')
        return redirect(url_for('inventory.admin_db'))
        
    return render_template('inventory/edit_product.html', product=product)

@inventory_bp.route('/admin/product/<int:id>/delete', methods=['POST'])
@admin_password_required
def delete_product(id):
    from app.models import Product, ActivityLog
    from flask_login import current_user
    product = Product.query.get_or_404(id)
    
    product.is_deleted = True
    log = ActivityLog(user_id=current_user.id, action=f"Deleted product {product.name}")
    db.session.add(log)
    db.session.commit()
    flash(f'Product {product.name} moved to trash (Soft Deleted).', 'success')
    return redirect(url_for('inventory.admin_db'))

@inventory_bp.route('/admin/product/<int:id>/retrieve', methods=['POST'])
@admin_password_required
def retrieve_product(id):
    from app.models import Product, ActivityLog
    from flask_login import current_user
    product = Product.query.get_or_404(id)
    
    product.is_deleted = False
    log = ActivityLog(user_id=current_user.id, action=f"Retrieved (Restored) product {product.name}")
    db.session.add(log)
    db.session.commit()
    flash(f'Product {product.name} successfully retrieved.', 'success')
    return redirect(url_for('inventory.admin_db'))

@inventory_bp.route('/admin/user/<int:id>/delete', methods=['POST'])
@admin_password_required
def delete_user(id):
    from app.models import User, ActivityLog
    from flask_login import current_user
    user = User.query.get_or_404(id)
    if user.email == 'bright12@gmail.com':
        flash('Cannot delete the primary admin account!', 'danger')
        return redirect(url_for('inventory.admin_db'))
        
    user.is_deleted = True
    log = ActivityLog(user_id=current_user.id, action=f"Deleted user {user.username}")
    db.session.add(log)
    db.session.commit()
    flash(f'User {user.username} suspended (Soft Deleted).', 'success')
    return redirect(url_for('inventory.admin_db'))

@inventory_bp.route('/admin/user/<int:id>/retrieve', methods=['POST'])
@admin_password_required
def retrieve_user(id):
    from app.models import User, ActivityLog
    from flask_login import current_user
    user = User.query.get_or_404(id)
    
    user.is_deleted = False
    log = ActivityLog(user_id=current_user.id, action=f"Retrieved (Restored) user {user.username}")
    db.session.add(log)
    db.session.commit()
    flash(f'User {user.username} restored successfully.', 'success')
    return redirect(url_for('inventory.admin_db'))

@inventory_bp.route('/admin/user/<int:id>/hard_delete', methods=['POST'])
@admin_password_required
def hard_delete_user(id):
    from app.models import User, Product, Order, ActivityLog, AuditLog, InventoryMovement, Sale
    from flask_login import current_user
    user = User.query.get_or_404(id)
    if user.email == 'bright12@gmail.com':
        flash('Cannot delete the primary admin account!', 'danger')
        return redirect(url_for('inventory.admin_db'))
        
    username = user.username
    
    # Manually cascade delete associated records
    products = Product.query.filter_by(supplier_id=user.id).all()
    product_ids = [p.id for p in products]
    
    if product_ids:
        Sale.query.filter(Sale.product_id.in_(product_ids)).delete(synchronize_session=False)
        InventoryMovement.query.filter(InventoryMovement.product_id.in_(product_ids)).delete(synchronize_session=False)
        Order.query.filter(Order.product_id.in_(product_ids)).delete(synchronize_session=False)
        Product.query.filter(Product.id.in_(product_ids)).delete(synchronize_session=False)
        
    Order.query.filter_by(supplier_id=user.id).delete(synchronize_session=False)
    InventoryMovement.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    ActivityLog.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    AuditLog.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    
    db.session.delete(user)
    
    log = ActivityLog(user_id=current_user.id, action=f"Hard Deleted user {username} and all associated records")
    db.session.add(log)
    db.session.commit()
    
    flash(f'User {username} completely deleted from the database.', 'success')
    return redirect(url_for('inventory.admin_db'))

@inventory_bp.route('/admin/activity-log')
@admin_password_required
def activity_logs():
    from app.models import ActivityLog
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(100).all()
    return render_template('inventory/activity_logs.html', logs=logs)

@inventory_bp.route('/movements')
@login_required
def movements():
    from app.models import InventoryMovement
    movements = InventoryMovement.query.order_by(InventoryMovement.timestamp.desc()).all()
    return render_template('inventory/movements.html', movements=movements)

@inventory_bp.route('/reports')
@login_required
def reports():
    from app.models import Product, Sale
    products = Product.query.filter_by(is_deleted=False).all()
    sales = Sale.query.all()
    
    total_inventory_value = sum(p.quantity * p.unit_price for p in products)
    total_sales_revenue = sum(s.quantity_sold * s.sale_price for s in sales)
    
    # Turnover calculation roughly: Cost of Goods Sold / Average Inventory
    # Here we can simplify to showing Sales Revenue vs Inventory Value
    
    return render_template('inventory/reports.html', 
                           products=products, 
                           total_inventory_value=total_inventory_value,
                           total_sales_revenue=total_sales_revenue)

@inventory_bp.route('/messages')
@login_required
def messages():
    from app.models import Message
    from flask_login import current_user
    # Ensure only admin can access this if it's admin inbox, or let it be generic inbox
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('inventory.dashboard'))
        
    inbox_messages = Message.query.filter_by(recipient_id=current_user.id).order_by(Message.timestamp.desc()).all()
    return render_template('inventory/messages.html', messages=inbox_messages)

@inventory_bp.route('/messages/<int:id>/read', methods=['POST'])
@login_required
def mark_message_read(id):
    from app.models import Message
    from flask_login import current_user
    if current_user.role != 'admin':
        return redirect(url_for('inventory.dashboard'))
    msg = Message.query.filter_by(id=id, recipient_id=current_user.id).first_or_404()
    msg.is_read = True
    db.session.commit()
    return redirect(url_for('inventory.messages'))
