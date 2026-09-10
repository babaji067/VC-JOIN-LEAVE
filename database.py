from pymongo import MongoClient
from config import MONGO_URL

# MongoDB connection
client = MongoClient(MONGO_URL)

db = client["vc_tracker"]

# Collections
sessions = db["vc_sessions"]
active_sessions = db["active_sessions"]


def start_session(
    user_id,
    name,
    username,
    chat_id,
    chat_title,
    join_time
):
    """
    User ke VC join hone par active session save karega.
    """

    data = {
        "user_id": user_id,
        "name": name,
        "username": username,
        "chat_id": chat_id,
        "chat_title": chat_title,
        "join_time": join_time,
        "leave_time": None,
        "duration": None
    }

    result = active_sessions.insert_one(data)

    return result.inserted_id


def end_session(user_id, chat_id, leave_time, duration):
    """
    User ke VC se leave hone par active session ko
    complete history me save karega.
    """

    session = active_sessions.find_one({
        "user_id": user_id,
        "chat_id": chat_id
    })

    if not session:
        return None

    session["leave_time"] = leave_time
    session["duration"] = duration

    # Active session remove
    active_sessions.delete_one({
        "_id": session["_id"]
    })

    # Complete history save
    result = sessions.insert_one(session)

    return result.inserted_id


def get_user_history(user_id, chat_id=None, start_time=None):
    """
    User ki VC history return karega.
    """

    query = {
        "user_id": user_id
    }

    if chat_id is not None:
        query["chat_id"] = chat_id

    if start_time is not None:
        query["join_time"] = {
            "$gte": start_time
        }

    return list(
        sessions.find(query)
        .sort("join_time", -1)
    )


def get_active_session(user_id, chat_id):
    """
    Check karega user abhi VC me tracked hai ya nahi.
    """

    return active_sessions.find_one({
        "user_id": user_id,
        "chat_id": chat_id
    })