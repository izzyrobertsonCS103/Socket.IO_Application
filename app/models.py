from app.db import db
from datetime import datetime


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    dob = db.Column(db.Date, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Friends(db.Model):
    __tablename__ = 'Friends'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False)
    friend_id = db.Column(db.Integer, nullable=False)


class Request(db.Model):
    __tablename__ = 'Request'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False)         # user_id has sent a friend request to friend_id
    friend_id = db.Column(db.Integer, nullable=False)


class Message(db.Model):
    __tablename__ = 'Message'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    source_user_id = db.Column(db.Integer, nullable=False)
    destination_user_id = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow().date(), nullable=False)
    time = db.Column(db.Time, default=datetime.utcnow().time(), nullable=False)
    message_type = db.Column(db.String(255), nullable=False)
    message_text = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(255), nullable=False)


class Group(db.Model):
    __tablename__ = 'group'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)


class UserGroup(db.Model):
    __tablename__ = 'UserGroup'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)


class GroupMessage(db.Model):
    __tablename__ = 'GroupMessage'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow().date(), nullable=False)
    time = db.Column(db.Time, default=datetime.utcnow().time(), nullable=False)
    message_type = db.Column(db.String(255), nullable=False)
    message_text = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(255), nullable=False)
    