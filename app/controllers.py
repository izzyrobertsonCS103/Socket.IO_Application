from flask import request, jsonify, session
from app import app
from app.models import User, Friends, Request, Message, Group, GroupMessage, UserGroup
from app.db import db
from sqlalchemy import or_
from app import sio
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import os
from flask import send_from_directory
import uuid

"""
Current Online Users
key = user_id
value = sid
"""
online_users = {}


def get_sid(user_id):
    for key in online_users:
        sid = online_users[key]
        if key == user_id:
            return sid
    return None


def socket_emit_event(event, user_id, data):
    sid = get_sid(user_id)
    if sid:
        sio.emit(event, data, room=sid)


def broadcast_online_status(user_id, online):
    """
    Tell all the connected sockets, the user_id's online status
    """
    sio.emit('online_status', {'user_id': user_id, 'online': online})

"""
Socket Routes
"""

@sio.event
def connect(sid, environ):
    print(f"Client connected: {sid}", online_users)


@sio.event
def disconnect(sid):
    for key in online_users:
        if online_users[key] == sid:
            del online_users[key]
            print("Deleted: ", key, sid)
            broadcast_online_status(key, False)
            break
    
    print(f"Client disconnected: {sid}", online_users)


@sio.event
def message(sid, data):
    print(f"Received message from {sid}: {data}")
    sio.send(sid, "Message received!")


@sio.event
def user_online(sid, data):
    userid = data['userid']
    online_users[userid] = sid
    broadcast_online_status(userid, True)
    print(f"{userid} is Online", online_users)


"""
HTTP Routes
"""


@app.route('/')
def serve_index():
    print("home page index called")
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)


@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        first_name = data['firstName']
        last_name = data['lastName']
        dob = data['dob']
        email = data['email']
        password = data['password']
        new_user = User(first_name=first_name, last_name=last_name, dob=dob, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'User registered successfully'}), 201
    except Exception as e:
        print(e)
        return jsonify({'message': 'Internal Server Error'}), 500
    

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data['email']
        password = data['password']
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['userid'] = user.id
            return jsonify({'message': 'Login successful'}), 200
        else:
            return jsonify({'error': 'Invalid username or password'}), 401
    except Exception as e:
        print(e)
        return jsonify({'error': 'Internal Server Error'}), 500
    

@app.route('/user', methods=['GET'])
def user():
    try:
        if 'userid' in session:
            userid = session['userid']
            user = User.query.get(userid)
            if user:
                return jsonify({
                    'firstName': user.first_name,
                    'lastName': user.last_name,
                    'dob': str(user.dob),
                    'email': user.email,
                    'userid': userid,
                    'id': userid,
                }), 200
            else:
                return jsonify({'error': 'User not found'}), 404
        else:
            return jsonify({'error': 'Unauthorized'}), 401
    except Exception as e:
        return jsonify({'error': 'Internal Server Error'}), 500
    

@app.route('/logout', methods=['POST'])
def logout():
    try:
        del session['userid']
        return jsonify({'message': 'Logout successful'}), 200
    except Exception as e:
        print(e)
        return jsonify({'error': 'Internal Server Error'}), 500


@app.route('/search/<name>', methods=['GET'])
def search_users(name):
    print(online_users)

    try:
        current_user_id = session.get('userid')

        if not current_user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        search_results = (
            User.query.filter(or_(User.first_name.ilike(f'{name}%'), User.last_name.ilike(f'{name}%')))
            .all()
        )

        results = []

        for result in search_results:

            if result.id == current_user_id:
                continue

            # Check if the found user is a friend of the current user
            friendship = Friends.query.filter(
                ((Friends.user_id == current_user_id) & (Friends.friend_id == result.id)) |
                ((Friends.user_id == result.id) & (Friends.friend_id == current_user_id))
            ).first()

            if friendship:
                status = 'FRIEND'
            else:
                # Check if there is a friend request
                friend_request_sent = Request.query.filter_by(user_id=current_user_id, friend_id=result.id).first()
                friend_request_received = Request.query.filter_by(user_id=result.id, friend_id=current_user_id).first()

                if friend_request_received:
                    status = 'ACCEPT_REQUEST'
                elif friend_request_sent:
                    status = 'REQUEST_SENT'
                else:
                    status = 'SEND_REQUEST'

            results.append({
                'firstName': result.first_name,
                'lastName': result.last_name,
                'status': status,
                'id': result.id,
                'online': online_users.get(result.id) != None
            })

        return jsonify({'results': results}), 200

    except Exception as e:
        print(e)
        return jsonify({'error': 'Internal Server Error'}), 500
    

@app.route('/sendrequest', methods=['POST'])
def send_request():
    try:
        # Get the current user's ID from the session
        current_user_id = session.get('userid')

        if not current_user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        friend_id = request.json.get('id')

        # Current user has sent a friend request to friend_id
        # Now we need to send the current_user details to friend_id, that you received a friend request.
        current_user_info = User.query.get(current_user_id)
        current_user_info = {
            'status': 'FRIEND_REQUEST_RECEIVED',
            'id': current_user_info.id,
            'firstName': current_user_info.first_name,
            'lastName': current_user_info.last_name,
            'online': get_sid(current_user_info.id) != None,
            'messages': []
        }

        friend_user_info = User.query.get(friend_id)
        friend_user_info = {
            'status': 'FRIEND_REQUEST_SENT',
            'id': friend_user_info.id,
            'firstName': friend_user_info.first_name,
            'lastName': friend_user_info.last_name,
            'online': get_sid(friend_user_info.id) != None,
            'messages': []
        }


        # Check if the friend request already exists
        existing_request = Request.query.filter_by(user_id=current_user_id, friend_id=friend_id).first()

        if not existing_request:
            new_request = Request(user_id=current_user_id, friend_id=friend_id)
            db.session.add(new_request)
            db.session.commit()
            
            socket_emit_event('add_user', friend_id, current_user_info)
            socket_emit_event('add_user', current_user_id, friend_user_info)

        return jsonify({'message': 'Friend request sent successfully'}), 200

    except Exception as e:
        print(e)
        return jsonify({'error': "Internal Server Error"}), 500
    

@app.route('/acceptrequest', methods=['POST'])
def accept_request():
    try:
        # Get the current user's ID from the session
        current_user_id = session.get('userid')

        if not current_user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        friend_id = request.json.get('id')

        # Remove friend request
        friend_request_1 = Request.query.filter_by(user_id=current_user_id, friend_id=friend_id).first()
        friend_request_2 = Request.query.filter_by(user_id=friend_id, friend_id=current_user_id).first()
        if friend_request_1:
            db.session.delete(friend_request_1)
        if friend_request_2:
            db.session.delete(friend_request_2)

        # Add entries to the Friends table
        new_friendship_1 = Friends(user_id=current_user_id, friend_id=friend_id)
        new_friendship_2 = Friends(user_id=friend_id, friend_id=current_user_id)
        db.session.add(new_friendship_1)
        db.session.add(new_friendship_2)
        db.session.commit()

        # Now we will emit a message saying that current_user and friend_id are friends.
        socket_emit_event('update_status', current_user_id, {'user_id': friend_id, 'status': 'FRIEND'})
        socket_emit_event('update_status', friend_id, {'user_id': current_user_id, 'status': 'FRIEND'})


        return jsonify({'message': 'Friend request accepted successfully'}), 200

    except Exception as e:
        print(e)
        return jsonify({'error': "Internal Server Error"}), 500


@app.route('/pendingrequests', methods=['GET'])
def pending_requests():
    try:
        # Get the current user's ID from the session
        current_user_id = session.get('userid')

        if not current_user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        # Retrieve pending friend requests for the current user
        friend_requests = Request.query.filter_by(friend_id=current_user_id).all()

        results = []

        for request_info in friend_requests:
            user_info = User.query.filter_by(id=request_info.user_id).first()
            results.append({
                'id': user_info.id,
                'firstName': user_info.first_name,
                'lastName': user_info.last_name,
            })

        return jsonify({'results': results}), 200

    except Exception as e:
        print("Error", e)
        return jsonify({'error': "Internal Server Error"}), 500


def retrieve_conversation(user_id1, user_id2):
    conversations = Message.query.filter(
        ((Message.source_user_id == user_id1) & (Message.destination_user_id == user_id2)) |
        ((Message.source_user_id == user_id2) & (Message.destination_user_id == user_id1))
    ).all()

    results = []
    for conversation in conversations:
        src_id = conversation.source_user_id
        dst_id = conversation.destination_user_id
        formatted_date = format_relative_date(conversation.date)
        formatted_time = conversation.time.strftime('%I:%M %p')
        results.append({
            'src_id': src_id,
            'dst_id': dst_id,
            'date': formatted_date,
            'time': formatted_time,
            'message': conversation.message_text,
            'type': conversation.message_type,
            'filepath': conversation.filepath,
        })
    return results


def retreive_friends(user_id):
    friends_info = Friends.query.filter_by(user_id=user_id).all()
    results = []
    for friend_info in friends_info:
        friend_user = User.query.filter_by(id=friend_info.friend_id).first()
        results.append({
            'status': 'FRIEND',
            'id': friend_user.id,
            'firstName': friend_user.first_name,
            'lastName': friend_user.last_name,
            'online': online_users.get(friend_user.id) != None,
            'messages': retrieve_conversation(user_id, friend_user.id)
        })
    return results


def retreive_received_requests(user_id):
    friend_requests = Request.query.filter_by(friend_id=user_id).all()
    results = []
    for request_info in friend_requests:
        user_info = User.query.filter_by(id=request_info.user_id).first()
        results.append({
            'status': 'FRIEND_REQUEST_RECEIVED',
            'id': user_info.id,
            'firstName': user_info.first_name,
            'lastName': user_info.last_name,
            'online': online_users.get(user_info.id) != None,
            'messages': []
        })
    return results


def retreive_sent_requests(user_id):
    friend_requests = Request.query.filter_by(user_id=user_id).all()
    results = []
    for request_info in friend_requests:
        user_info = User.query.filter_by(id=request_info.friend_id).first()
        results.append({
            'status': 'FRIEND_REQUEST_SENT',
            'id': user_info.id,
            'firstName': user_info.first_name,
            'lastName': user_info.last_name,
            'online': online_users.get(user_info.id) != None,
            'messages': []
        })
    return results


# Route for retrieving all friends of the current user
@app.route('/friends', methods=['GET'])
def get_friends():
    try:
        # Get the current user's ID from the session
        current_user_id = session.get('userid')

        if not current_user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        # Retrieve all friends of the current user from the Friends table
        friends_info = Friends.query.filter_by(user_id=current_user_id).all()

        results = []

        for friend_info in friends_info:
            friend_user = User.query.filter_by(id=friend_info.friend_id).first()
            results.append({
                'id': friend_user.id,
                'firstName': friend_user.first_name,
                'lastName': friend_user.last_name,
            })

        return jsonify({'results': results}), 200

    except Exception as e:
        print(e)
        return jsonify({'error': "Internal Server Error"}), 500
    

@app.route('/data', methods=['GET'])
def get_data():
    try:
        current_user_id = session.get('userid')
        if not current_user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        data = []

        friends = retreive_friends(current_user_id)
        received_request = retreive_received_requests(current_user_id)
        sent_request = retreive_sent_requests(current_user_id)

        print(friends)
        print(received_request)
        print(sent_request)

        data.extend(received_request)

        # If both the users sent a request to each other, we will not add
        # that to the sent request. The request will be already present in the received_request.
        done = set(x['id'] for x in received_request)
        data.extend([x for x in sent_request if x['id'] not in done])
        data.extend(friends)

        # group data
        group_data = get_groups(current_user_id)
        print(group_data, current_user_id)

        return jsonify({'data': data, 'groups': group_data}), 200
        
    except Exception as e:
        print(e)
        return jsonify({'error': "Internal Server Error"}), 500


def format_relative_date(message_date):
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)

    if message_date == today:
        return 'Today'
    elif message_date == yesterday:
        return 'Yesterday'
    else:
        return message_date.strftime('%d/%m/%Y')
    

# API endpoint for posting messages
# Added Later to upload files
@app.route('/sendmessagefile', methods=['POST'])
def post_message_file():
    try:
        current_user_id = session.get('userid')
        if not current_user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        print(request.form, request.files)

        destination_user_id = request.form.get('destination_user_id')
        fileData = request.files.get("file")
        message_text = secure_filename(fileData.filename)
        upload_filename = str(uuid.uuid4())

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], upload_filename)
        fileData.save(filepath)
        message_type = "file"

        relative_filepath = '/uploads/' + upload_filename

        # Create a new message
        new_message = Message(
            source_user_id=current_user_id,
            destination_user_id=destination_user_id,
            message_text=message_text,
            message_type=message_type,
            filepath=relative_filepath,
        )

        # Add the message to the database
        db.session.add(new_message)
        db.session.commit()

        # Notify using websocket
        added_message = Message.query.get(new_message.id)
        formatted_date = format_relative_date(added_message.date)
        formatted_time = added_message.time.strftime('%I:%M %p')
        result1 = {
            'src_id': added_message.source_user_id,
            'dst_id': added_message.destination_user_id,
            'date': formatted_date,
            'time': formatted_time,
            'message': added_message.message_text,
            'type': added_message.message_type,
            'filepath': added_message.filepath,
        }

        result2 = {
            'src_id': added_message.source_user_id,
            'dst_id': added_message.destination_user_id,
            'date': formatted_date,
            'time': formatted_time,
            'message': added_message.message_text,
            'type': added_message.message_type,
            'filepath': added_message.filepath,
        }

        socket_emit_event('add_message', added_message.source_user_id, result1)
        socket_emit_event('add_message', added_message.destination_user_id, result2)

        return jsonify({'message': 'Message sent successfully'}), 201

    except Exception as e:
        print(e)
        return jsonify({'error': 'Internal Server Error'}), 500


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    print("YES")
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# API endpoint for posting messages
@app.route('/sendmessage', methods=['POST'])
def post_message():
    try:
        current_user_id = session.get('userid')
        if not current_user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.json
        destination_user_id = data.get('destination_user_id')
        message_text = data.get('message_text')
        message_type = 'text'
        filepath = ""

        new_message = Message(
            source_user_id=current_user_id,
            destination_user_id=destination_user_id,
            message_text=message_text,
            message_type=message_type,
            filepath=filepath,
        )

        # Add the message to the database
        db.session.add(new_message)
        db.session.commit()

        # Notify using websocket
        added_message = Message.query.get(new_message.id)
        formatted_date = format_relative_date(added_message.date)
        formatted_time = added_message.time.strftime('%I:%M %p')
        result1 = {
            'src_id': added_message.source_user_id,
            'dst_id': added_message.destination_user_id,
            'date': formatted_date,
            'time': formatted_time,
            'message': added_message.message_text,
            'type': added_message.message_type,
            'filepath': added_message.filepath,
        }

        result2 = {
            'src_id': added_message.source_user_id,
            'dst_id': added_message.destination_user_id,
            'date': formatted_date,
            'time': formatted_time,
            'message': added_message.message_text,
            'type': added_message.message_type,
            'filepath': added_message.filepath,
        }

        socket_emit_event('add_message', added_message.source_user_id, result1)
        socket_emit_event('add_message', added_message.destination_user_id, result2)

        return jsonify({'message': 'Message sent successfully'}), 201

    except Exception as e:
        print(e)
        return jsonify({'error': 'Internal Server Error'}), 500


def get_groups(user_id):
    """
    Generate all the groups for the user
    """
    user_groups = UserGroup.query.filter_by(user_id=user_id).all()
    groups_data = []

    for user_group in user_groups:
        group_users = UserGroup.query.filter_by(group_id=user_group.group_id).all()
        user_ids = [group_user.user_id for group_user in group_users]

        group_info = {
            'group_id': user_group.group_id,
            'group_name': Group.query.get(user_group.group_id).name,
            'users': user_ids,
            'messages': [
                {
                    'user_id': message.user_id,
                    'date': format_relative_date(message.date),
                    'time': message.time.strftime('%I:%M %p'),
                    'message': message.message_text,
                    'name': f"{User.query.get(message.user_id).first_name}  {User.query.get(message.user_id).last_name}",
                    'type': message.message_type,
                    'filepath': message.filepath,
                }
                for message in GroupMessage.query.filter_by(group_id=user_group.group_id).all()
            ]
        }
        groups_data.append(group_info)

    return groups_data


# Add this route for creating a group
@app.route('/creategroup', methods=['POST'])
def create_group():
    try:
        data = request.json
        user_ids = data.get('user_ids')
        group_name = data.get('group_name')
        new_group = Group(name=group_name)
        print("Creating Group: ", group_name, new_group.name)
        db.session.add(new_group)
        db.session.commit()
        for user_id in user_ids:
            user_group = UserGroup(user_id=user_id, group_id=new_group.id)
            db.session.add(user_group)
        db.session.commit()

        # Notify Everybody
        for user_id in user_ids:
            print("Sending to: ", user_id)
            socket_emit_event("new_group", user_id, {
                "id": new_group.id,
                "group_name": new_group.name,
                "messages": [],
                "users": user_ids
            })

        return jsonify({'message': 'Group created successfully'}), 201
    except Exception as e:
        print(e)
        return jsonify({'error': 'Internal Server Error'}), 500


def get_group_members(group_id):
    try:
        members = UserGroup.query.filter_by(group_id=group_id).all()
        user_ids = [member.user_id for member in members]
        return user_ids
    except Exception as e:
        print(e)
        return []
    

# API endpoint for posting files to group
@app.route('/sendfilegroup', methods=['POST'])
def post_group_message_file():
    try:
        current_user_id = session.get('userid')
        if not current_user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        print(request.form, request.files)

        group_id = request.form.get('group_id')
        sender = request.form.get('sender')
        fileData = request.files.get("file")
        message_text = secure_filename(fileData.filename)
        upload_filename = str(uuid.uuid4())
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], upload_filename)
        fileData.save(filepath)
        message_type = "file"
        relative_filepath = '/uploads/' + upload_filename

        # Insert the message into the GroupMessage table
        new_message = GroupMessage(
            group_id=group_id,
            user_id=sender,
            date=datetime.utcnow().date(),
            time=datetime.utcnow().time(),
            message_type=message_type,
            message_text=message_text,
            filepath=relative_filepath,
        )
        
        db.session.add(new_message)
        db.session.commit()

        # Notify all members of the group using WebSocket
        members = get_group_members(group_id)
        for member_id in members:
            user = User.query.get(member_id)
            name = f"{user.first_name} {user.last_name}"
            socket_emit_event("group_message", member_id, {
                'group_id': group_id,
                'user_id': sender,
                'date': format_relative_date(new_message.date),
                'time': new_message.time.strftime('%I:%M %p'),
                'message': message_text,
                'name': name,
                'type': message_type,
                'filepath': relative_filepath,
            });
        
        return jsonify({'message': 'Message sent successfully'}), 201

    except Exception as e:
        print(e)
        return jsonify({'error': 'Internal Server Error'}), 500


# Define the /sendmessagegroup endpoint
@app.route('/sendmessagegroup', methods=['POST'])
def send_message_group():
    try:
        # Get data from the request
        data = request.json
        group_id = data.get('group_id')
        sender = data.get('sender')
        message_text = data.get('message_text')

        # Insert the message into the GroupMessage table
        new_message = GroupMessage(
            group_id=group_id,
            user_id=sender,
            date=datetime.utcnow().date(),
            time=datetime.utcnow().time(),
            message_type='text',
            message_text=message_text,
            filepath='',
        )
        db.session.add(new_message)
        db.session.commit()

        # Notify all members of the group using WebSocket
        members = get_group_members(group_id)
        for member_id in members:
            user = User.query.get(member_id)
            name = f"{user.first_name} {user.last_name}"
            socket_emit_event("group_message", member_id, {
                'group_id': group_id,
                'user_id': sender,
                'date': format_relative_date(new_message.date),
                'time': new_message.time.strftime('%I:%M %p'),
                'message': message_text,
                'name': name,
                'type': 'text',
                'filepath': '',
            });

        return jsonify({'message': 'Group message sent successfully'}), 201

    except Exception as e:
        print(e)
        return jsonify({'error': 'Internal Server Error'}), 500

