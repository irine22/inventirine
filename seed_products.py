from app import create_app, db
from app.models import Product, Supplier, Sale, InventoryMovement
import random

def seed_products():
    app = create_app()
    with app.app_context():
        # Clear existing tables to avoid duplicates
        Sale.query.delete()
        InventoryMovement.query.delete()
        Product.query.delete()
        Supplier.query.delete()
        
        # Create a sample supplier
        supplier = Supplier(name="GlobalTech Solutions", contact_email="sales@globaltech.com", phone="+237-123-456")
        db.session.add(supplier)
        db.session.commit()

        # Sample Products
        products_data = [
            {"name": "UltraBook Pro 15", "sku": "LAP-UB-001", "price": 850000, "qty": 15, "loc": "Warehouse A"},
            {"name": "SmartPhone X10", "sku": "PHN-SX-010", "price": 450000, "qty": 5, "loc": "Warehouse B"},
            {"name": "Wireless Headphones", "sku": "AUD-WH-005", "price": 75000, "qty": 24, "loc": "Warehouse A"},
            {"name": "Gaming Monitor 27", "sku": "MON-GM-27", "price": 220000, "qty": 8, "loc": "Warehouse C"},
            {"name": "USB-C Hub 8-in-1", "sku": "ACC-USB-08", "price": 35000, "qty": 50, "loc": "Warehouse B"},
            {"name": "Mechanical Keyboard", "sku": "ACC-KB-MECH", "price": 65000, "qty": 2, "loc": "Warehouse A"}
        ]

        products_list = []
        for p_data in products_data:
            product = Product(
                name=p_data["name"],
                sku=p_data["sku"],
                unit_price=p_data["price"],
                quantity=p_data["qty"],
                location=p_data["loc"],
                category="Electronics",
                supplier_id=supplier.id
            )
            db.session.add(product)
            db.session.commit()
            
            # Initial stock movement
            movement = InventoryMovement(
                product_id=product.id,
                movement_type="purchase",
                quantity_change=p_data["qty"],
                notes="Initial stock arrival"
            )
            db.session.add(movement)
            
            products_list.append(product)
        
        db.session.commit()

        # Seed sample sales
        # Find products to create sales for
        smartphone = Product.query.filter_by(sku="PHN-SX-010").first()
        ultrabook = Product.query.filter_by(sku="LAP-UB-001").first()
        usb_hub = Product.query.filter_by(sku="ACC-USB-08").first()

        if smartphone and ultrabook and usb_hub:
            sale1 = Sale(product_id=smartphone.id, quantity_sold=2, sale_price=450000)
            sale2 = Sale(product_id=ultrabook.id, quantity_sold=1, sale_price=850000)
            sale3 = Sale(product_id=usb_hub.id, quantity_sold=5, sale_price=35000)
            
            m1 = InventoryMovement(product_id=smartphone.id, movement_type="sale", quantity_change=-2, notes="Sold to customer")
            m2 = InventoryMovement(product_id=ultrabook.id, movement_type="sale", quantity_change=-1, notes="Sold to customer")
            m3 = InventoryMovement(product_id=usb_hub.id, movement_type="sale", quantity_change=-5, notes="Sold to customer")
            
            db.session.add_all([sale1, sale2, sale3, m1, m2, m3])
            db.session.commit()

        print("Database successfully connected and populated with inventory & transactional data!")

if __name__ == "__main__":
    seed_products()
