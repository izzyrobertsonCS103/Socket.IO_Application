from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.declarative import declarative_base
from .db import db
from flask_cors import CORS
import socketio
import os

app = Flask(__name__, static_folder='dist', static_url_path='')
app.secret_key = 'slfjslkfj90f809sdfksjf09sudfoijsdf980ujsdoifj980'

# Using sql server
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqldb://root:csgo@localhost/sent'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqldb://root:@localhost/messaging_app_db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'app/uploads')
CORS(app, supports_credentials=True)
db.init_app(app)
sio = socketio.Server(cors_allowed_origins='*')
app.wsgi_app = socketio.WSGIApp(sio, app.wsgi_app)
