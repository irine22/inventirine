from app import create_app, db
from app.models import User, Order

app = create_app()
with app.app_context():
    user_6 = db.session.get(User, 6)  # Trans Joy - transjoy23@gmai.com (typo, logged-in user)
    user_7 = db.session.get(User, 7)  # Joy Trans - transjoy23@gmail.com (correct email, has orders)
    
    # Step 1: Change user 7's email first to free the unique constraint
    user_7.email = 'transjoy23_old@gmail.com'
    user_7.is_deleted = True
    db.session.flush()
    
    # Step 2: Fix user 6's email typo
    user_6.email = 'transjoy23@gmail.com'
    db.session.flush()
    
    # Step 3: Move all orders from user 7 to user 6
    orders = Order.query.filter_by(supplier_id=7).all()
    for o in orders:
        o.supplier_id = 6
        print(f"  Reassigned Order #{o.id} to Trans Joy (ID=6)")
    
    db.session.commit()
    
    # Verify
    orders_check = Order.query.filter_by(supplier_id=6).all()
    print(f"\nDone! Trans Joy (ID=6, email={user_6.email}) now has {len(orders_check)} orders")
