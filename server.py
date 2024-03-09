from app import app
from app.db import db
from app import models
from app import controllers
import eventlet

if __name__ == "__main__":
    with app.app_context():
        print("DB migraiton started")
        db.create_all()
        print("DB migration Done")

    eventlet.wsgi.server(eventlet.listen(('0.0.0.0', 5001)), app,)
