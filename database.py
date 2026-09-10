from pymongo import MongoClient, ASCENDING
from config import MONGO_URL

mongo = MongoClient(MONGO_URL)

db = mongo["vc_tracker"]

sessions = db["sessions"]
active_sessions = db["active_sessions"]

sessions.create_index([
    ("user_id", ASCENDING),
    ("chat_id", ASCENDING),
    ("join_time", ASCENDING)
])

active_sessions.create_index(
    [
        ("user_id", ASCENDING),
        ("chat_id", ASCENDING)
    ],
    unique=True
)


def start_session(
    user_id,
    name,
    username,
    chat_id,
    chat_title,
    join_time
):
    active_sessions.update_one(
        {
            "user_id": user_id,
            "chat_id": chat_id
        },
        {
            "$set": {
                "user_id": user_id,
                "name": name,
                "username": username,
                "chat_id": chat_id,
                "chat_title": chat_title,
                "join_time": join_time
            }
        },
        upsert=True
    )


def get_active(user_id, chat_id):
    return active_sessions.find_one({
        "user_id": user_id,
        "chat_id": chat_id
    })


def end_session(
    user_id,
    chat_id,
    leave_time
):
    session = get_active(
        user_id,
        chat_id
    )

    if not session:
        return None

    join_time = session["join_time"]

    duration = int(
        (leave_time - join_time).total_seconds()
    )

    session["leave_time"] = leave_time
    session["duration_seconds"] = duration

    sessions.insert_one(session)

    active_sessions.delete_one({
        "_id": session["_id"]
    })

    return session


def get_sessions(
    user_id,
    chat_id,
    start_time
):
    return list(
        sessions.find({
            "user_id": user_id,
            "chat_id": chat_id,
            "join_time": {
                "$gte": start_time
            }
        }).sort(
            "join_time",
            -1
        )
    )