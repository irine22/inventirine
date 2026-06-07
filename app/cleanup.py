# cleanup.py – delete all users except admin
# Run with: python -c "import os; os.chdir('c:/Users/Administrator/Desktop/invent'); from app import create_app, db; from app.models import User; app=create_app(); with app.app_context(): User.query.filter(User.role!='admin').delete(synchronize_session=False); db.session.commit()"
