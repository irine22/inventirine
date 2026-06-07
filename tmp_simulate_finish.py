from app import create_app
from app.models import User, Product, InventoryMovement, db
from app.utils import log_audit

app = create_app()
with app.app_context():
    supplier = User.query.filter_by(id=6, role='supplier', is_deleted=False).first()
    if not supplier:
        raise SystemExit('Supplier with id=6 not found')

    product = Product.query.filter_by(supplier_id=supplier.id, sku='TEST-FINISH-1').first()
    if product is None:
        product = Product(
            name='Test Finish Product',
            sku='TEST-FINISH-1',
            category='Test',
            unit_price=1.0,
            quantity=10,
            reorder_threshold=1,
            description='Temp test product',
            supplier_id=supplier.id
        )
        db.session.add(product)
        db.session.commit()
        print('Created product', product.id)
    else:
        print('Existing product', product.id)

    print('Before quantity:', product.quantity)
    if product.quantity != 0:
        old_qty = product.quantity
        product.quantity = 0
        log_audit('product', product.id, 'quantity', old_qty, 0, supplier.id)
        movement = InventoryMovement(
            product_id=product.id,
            movement_type='adjustment',
            quantity_change=-old_qty,
            user_id=supplier.id,
            notes='Marked as finished by supplier - simulation'
        )
        db.session.add(movement)
        db.session.commit()
        print('After quantity:', product.quantity)
    else:
        print('Product already finished')
