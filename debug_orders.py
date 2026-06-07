from app import create_app, db
from app.models import User, Order

app = create_app()
with app.app_context():
    # Show all suppliers
    print("=== ALL SUPPLIERS ===")
    suppliers = User.query.filter_by(role='supplier').all()
    for s in suppliers:
        print(f"  ID={s.id}, username={s.username}, email={s.email}, company={s.company_name}, is_deleted={s.is_deleted}")

    # Show all orders
    print("\n=== ALL ORDERS ===")
    orders = Order.query.all()
    if not orders:
        print("  No orders in the database at all.")
    for o in orders:
        supplier = User.query.get(o.supplier_id)
        print(f"  Order #{o.id}: product_id={o.product_id}, supplier_id={o.supplier_id} ({supplier.email if supplier else 'MISSING'}), qty={o.quantity}, status={o.status}")

    # Check transjoy specifically
    print("\n=== TRANSJOY CHECK ===")
    tj = User.query.filter_by(email='transjoy23@gmail.com').first()
    if tj:
        print(f"  Found: ID={tj.id}, role={tj.role}, is_deleted={tj.is_deleted}")
        tj_orders = Order.query.filter_by(supplier_id=tj.id).all()
        print(f"  Orders assigned to this supplier: {len(tj_orders)}")
        for o in tj_orders:
            print(f"    Order #{o.id}: qty={o.quantity}, status={o.status}")
    else:
        print("  transjoy23@gmail.com NOT FOUND in database!")
