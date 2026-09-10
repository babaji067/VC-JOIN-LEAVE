from pymongo import MongoClient, ASCENDING
from config import MONGO_URL


client = MongoClient(MONGO_URL)

db = client["telegram_vc_tracker"]

sessions = db["sessions"]
active = db["active"]


# Indexes
sessions.create_index(
    [
        ("user_id", ASCENDING),
        ("chat_id", ASCENDING),
        ("join_time", ASCENDING)
    ]
)

active.create_index(
    [
        ("user_id", ASCENDING),
        ("chat_id", ASCENDING)
    ],
    unique=True
)


def create_session(data):
    return active.update_one(
        {
            "user_id": data["user_id"],
            "chat_id": data["chat_id"]
        },
        {
            "$setOnInsert": data
        },
        upsert=True
    )


def get_active(user_id, chat_id):
    return active.find_one(
        {
            "user_id": user_id,
            "chat_id": chat_id
        }
    )


def finish_session(
    user_id,
    chat_id,
    leave_time,
    duration_seconds
):

    session = get_active(
        user_id,
        chat_id
    )

    if not session:
        return None

    session["leave_time"] = leave_time
    session["duration_seconds"] = duration_seconds

    sessions.insert_one(session)

    active.delete_one(
        {
            "_id": session["_id"]
        }
    )

    return session


def get_history(
    user_id,
    chat_id,
    start_time
):

    return list(
        sessions.find(
            {
                "user_id": user_id,
                "chat_id": chat_id,
                "join_time": {
                    "$gte": start_time
                }
            }
        ).sort(
            "join_time",
            -1
        )
    )


def get_count(
    user_id,
    chat_id,
    start_time
):

    return sessions.count_documents(
        {
            "user_id": user_id,
            "chat_id": chat_id,
            "join_time": {
                "$gte": start_time
            }
        }
    )