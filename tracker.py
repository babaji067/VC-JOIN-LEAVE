from datetime import datetime, timezone

from pyrogram import Client
from pyrogram.raw import types

from database import (
    start_session,
    get_active,
    end_session
)


def now():
    return datetime.now(timezone.utc)


def format_time(dt):
    return dt.strftime(
        "%d-%m-%Y %I:%M:%S %p"
    )


def format_duration(seconds):

    seconds = int(seconds)

    days, seconds = divmod(
        seconds,
        86400
    )

    hours, seconds = divmod(
        seconds,
        3600
    )

    minutes, seconds = divmod(
        seconds,
        60
    )

    result = []

    if days:
        result.append(
            f"{days}d"
        )

    if hours:
        result.append(
            f"{hours}h"
        )

    if minutes:
        result.append(
            f"{minutes}m"
        )

    if seconds or not result:
        result.append(
            f"{seconds}s"
        )

    return " ".join(result)


class VCTracker:

    def __init__(
        self,
        client: Client,
        logger
    ):

        self.client = client
        self.logger = logger

        # call_id -> chat_id
        self.call_map = {}

        # chat_id -> group title
        self.chat_titles = {}

    async def register_call(
        self,
        chat_id,
        call
    ):

        call_id = getattr(
            call,
            "id",
            None
        )

        if not call_id:
            return

        self.call_map[
            call_id
        ] = chat_id

        try:

            chat = await self.client.get_chat(
                chat_id
            )

            title = (
                chat.title
                or "Voice Chat"
            )

        except Exception:

            title = "Voice Chat"

        self.chat_titles[
            chat_id
        ] = title

        print(
            f"[VC REGISTERED] "
            f"{title} | {chat_id}"
        )

    async def handle_participant(
        self,
        call,
        participant,
        users
    ):

        call_id = getattr(
            call,
            "id",
            None
        )

        if not call_id:
            return

        chat_id = self.call_map.get(
            call_id
        )

        if not chat_id:
            return

        # Telegram Peer -> user ID
        peer = participant.peer

        if not isinstance(
            peer,
            types.PeerUser
        ):
            return

        user_id = peer.user_id

        # --------------------------------
        # USER OBJECT
        # --------------------------------

        user = users.get(
            user_id
        )

        if user:

            name = (
                f"{user.first_name or ''} "
                f"{user.last_name or ''}"
            ).strip()

            if not name:
                name = "Unknown User"

            username = user.username

        else:

            try:

                user = await self.client.get_users(
                    user_id
                )

                name = (
                    f"{user.first_name or ''} "
                    f"{user.last_name or ''}"
                ).strip()

                username = user.username

            except Exception:

                name = "Unknown User"
                username = None

        title = self.chat_titles.get(
            chat_id,
            "Voice Chat"
        )

        # --------------------------------
        # LEFT
        # --------------------------------

        if getattr(
            participant,
            "left",
            False
        ):

            session = get_active(
                user_id,
                chat_id
            )

            if not session:
                return

            leave_time = now()

            finished = end_session(
                user_id,
                chat_id,
                leave_time
            )

            if not finished:
                return

            duration = format_duration(
                finished[
                    "duration_seconds"
                ]
            )

            username_text = (
                f"@{username}"
                if username
                else "No username"
            )

            text = (
                "🔴 <b>VC USER LEFT</b>\n\n"

                f"👤 <b>Name:</b> {name}\n"
                f"🔗 <b>Username:</b> "
                f"{username_text}\n"
                f"🆔 <b>ID:</b> "
                f"<code>{user_id}</code>\n\n"

                f"🎙️ <b>Group:</b> "
                f"{title}\n\n"

                f"🟢 <b>Joined:</b> "
                f"{format_time(session['join_time'])}\n"

                f"🔴 <b>Left:</b> "
                f"{format_time(leave_time)}\n"

                f"⏱️ <b>Stayed:</b> "
                f"{duration}"
            )

            await self.logger(
                text
            )

            return

        # --------------------------------
        # JOIN
        # --------------------------------

        just_joined = getattr(
            participant,
            "just_joined",
            False
        )

        if not just_joined:
            return

        # Duplicate protection
        if get_active(
            user_id,
            chat_id
        ):
            return

        join_time = now()

        start_session(
            user_id=user_id,
            name=name,
            username=username,
            chat_id=chat_id,
            chat_title=title,
            join_time=join_time
        )

        username_text = (
            f"@{username}"
            if username
            else "No username"
        )

        text = (
            "🟢 <b>VC USER JOINED</b>\n\n"

            f"👤 <b>Name:</b> {name}\n"
            f"🔗 <b>Username:</b> "
            f"{username_text}\n"
            f"🆔 <b>ID:</b> "
            f"<code>{user_id}</code>\n\n"

            f"🎙️ <b>Group:</b> "
            f"{title}\n"

            f"🕐 <b>Joined:</b> "
            f"{format_time(join_time)}"
        )

        await self.logger(
            text
        )

    async def call_ended(
        self,
        call
    ):

        call_id = getattr(
            call,
            "id",
            None
        )

        if call_id:

            self.call_map.pop(
                call_id,
                None
            )

        print(
            f"[VC ENDED] {call_id}"
        )