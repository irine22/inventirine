from app import create_app
from app.models import User, Product

app = create_app()
with app.app_context():
    supps = User.query.filter_by(role='supplier', is_deleted=False).all()
    print('Suppliers:')
    for s in supps:
        print(s.id, s.username, s.email, s.company_name)
    print('--- Products ---')
    prods = Product.query.filter(Product.supplier_id.in_([s.id for s in supps])).all()
    for p in prods:
        print(p.id, p.name, 'supplier_id=', p.supplier_id, 'qty=', p.quantity, 'deleted=', p.is_deleted)
