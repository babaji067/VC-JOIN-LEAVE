import asyncio
from datetime import datetime, timezone

from pyrogram import Client
from pyrogram.raw import functions, types

from database import (
    create_session,
    get_active,
    finish_session
)


CHECK_INTERVAL = 5


def utc_now():
    return datetime.now(timezone.utc)


def format_duration(seconds):
    seconds = int(seconds)

    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    parts = []

    if days:
        parts.append(f"{days}d")

    if hours:
        parts.append(f"{hours}h")

    if minutes:
        parts.append(f"{minutes}m")

    if seconds or not parts:
        parts.append(f"{seconds}s")

    return " ".join(parts)


class VCTracker:

    def __init__(self, client: Client, log_callback=None):
        self.client = client
        self.log_callback = log_callback

        # chat_id -> InputGroupCall
        self.calls = {}

        # chat_id -> set(user_id)
        self.participants = {}

        # chat_id -> background task
        self.tasks = {}

    async def log(self, text):

        if self.log_callback:
            try:
                await self.log_callback(text)
            except Exception as e:
                print(f"LOG ERROR: {e}")

    # -----------------------------------------
    # START TRACKING A VC
    # -----------------------------------------

    async def start_call(
        self,
        chat_id,
        call,
        chat_title="Voice Chat"
    ):

        self.calls[chat_id] = call

        if chat_id not in self.participants:
            self.participants[chat_id] = set()

        if chat_id not in self.tasks:

            self.tasks[chat_id] = asyncio.create_task(
                self.tracking_loop(
                    chat_id,
                    chat_title
                )
            )

        print(
            f"[VC STARTED] "
            f"{chat_title} | {chat_id}"
        )

    # -----------------------------------------
    # STOP TRACKING
    # -----------------------------------------

    async def stop_call(self, chat_id):

        task = self.tasks.pop(
            chat_id,
            None
        )

        if task:
            task.cancel()

        self.calls.pop(
            chat_id,
            None
        )

        self.participants.pop(
            chat_id,
            None
        )

        print(
            f"[VC STOPPED] {chat_id}"
        )

    # -----------------------------------------
    # GET PARTICIPANTS
    # -----------------------------------------

    async def fetch_participants(self, chat_id):

        call = self.calls.get(chat_id)

        if not call:
            return set()

        try:

            result = await self.client.invoke(
                functions.phone.GetGroupParticipants(
                    call=call,
                    ids=[],
                    sources=[],
                    offset="",
                    limit=100
                )
            )

            current_users = set()

            for participant in result.participants:

                # left=True means user is no longer
                # an active participant.
                if getattr(
                    participant,
                    "left",
                    False
                ):
                    continue

                user_id = self.peer_to_user_id(
                    participant.peer
                )

                if user_id:
                    current_users.add(
                        user_id
                    )

            return current_users

        except Exception as e:

            print(
                f"[PARTICIPANT ERROR] "
                f"{chat_id}: {e}"
            )

            return set()

    # -----------------------------------------
    # PEER -> USER ID
    # -----------------------------------------

    @staticmethod
    def peer_to_user_id(peer):

        if isinstance(
            peer,
            types.PeerUser
        ):
            return peer.user_id

        return None

    # -----------------------------------------
    # USER INFO
    # -----------------------------------------

    async def get_user_info(self, user_id):

        try:

            user = await self.client.get_users(
                user_id
            )

            name = (
                f"{user.first_name or ''} "
                f"{user.last_name or ''}"
            ).strip()

            if not name:
                name = "Unknown User"

            username = user.username

            return (
                name,
                username
            )

        except Exception:

            return (
                "Unknown User",
                None
            )

    # -----------------------------------------
    # JOIN
    # -----------------------------------------

    async def handle_join(
        self,
        user_id,
        chat_id,
        chat_title
    ):

        active = get_active(
            user_id,
            chat_id
        )

        if active:
            return

        name, username = await self.get_user_info(
            user_id
        )

        join_time = utc_now()

        create_session(
            {
                "user_id": user_id,
                "name": name,
                "username": username,
                "chat_id": chat_id,
                "chat_title": chat_title,
                "join_time": join_time
            }
        )

        username_text = (
            f"@{username}"
            if username
            else "No username"
        )

        text = (
            "🟢 <b>VC JOIN</b>\n\n"
            f"👤 <b>Name:</b> {name}\n"
            f"🔗 <b>Username:</b> "
            f"{username_text}\n"
            f"🆔 <b>ID:</b> "
            f"<code>{user_id}</code>\n"
            f"🎙️ <b>Group:</b> "
            f"{chat_title}\n"
            f"🕐 <b>Joined:</b> "
            f"{join_time.strftime('%d-%m-%Y %I:%M:%S %p')}"
        )

        await self.log(text)

    # -----------------------------------------
    # LEAVE
    # -----------------------------------------

    async def handle_leave(
        self,
        user_id,
        chat_id,
        chat_title
    ):

        active = get_active(
            user_id,
            chat_id
        )

        if not active:
            return

        leave_time = utc_now()

        join_time = active["join_time"]

        seconds = int(
            (
                leave_time - join_time
            ).total_seconds()
        )

        duration = format_duration(
            seconds
        )

        finish_session(
            user_id=user_id,
            chat_id=chat_id,
            leave_time=leave_time,
            duration_seconds=seconds
        )

        username = active.get(
            "username"
        )

        username_text = (
            f"@{username}"
            if username
            else "No username"
        )

        text = (
            "🔴 <b>VC LEAVE</b>\n\n"
            f"👤 <b>Name:</b> "
            f"{active.get('name', 'Unknown')}\n"
            f"🔗 <b>Username:</b> "
            f"{username_text}\n"
            f"🆔 <b>ID:</b> "
            f"<code>{user_id}</code>\n"
            f"🎙️ <b>Group:</b> "
            f"{chat_title}\n\n"
            f"🟢 <b>Joined:</b> "
            f"{join_time.strftime('%d-%m-%Y %I:%M:%S %p')}\n"
            f"🔴 <b>Left:</b> "
            f"{leave_time.strftime('%d-%m-%Y %I:%M:%S %p')}\n"
            f"⏱️ <b>Stayed:</b> "
            f"{duration}"
        )

        await self.log(text)

    # -----------------------------------------
    # TRACKING LOOP
    # -----------------------------------------

    async def tracking_loop(
        self,
        chat_id,
        chat_title
    ):

        print(
            f"[TRACKING] "
            f"{chat_title}"
        )

        first_check = True

        while True:

            try:

                current = await self.fetch_participants(
                    chat_id
                )

                previous = self.participants.get(
                    chat_id,
                    set()
                )

                # First check:
                # Existing users ko "JOIN" mat count karo.
                if first_check:

                    self.participants[
                        chat_id
                    ] = current

                    first_check = False

                else:

                    joined = (
                        current - previous
                    )

                    left = (
                        previous - current
                    )

                    # -------------------------
                    # JOINED USERS
                    # -------------------------

                    for user_id in joined:

                        await self.handle_join(
                            user_id,
                            chat_id,
                            chat_title
                        )

                    # -------------------------
                    # LEFT USERS
                    # -------------------------

                    for user_id in left:

                        await self.handle_leave(
                            user_id,
                            chat_id,
                            chat_title
                        )

                    self.participants[
                        chat_id
                    ] = current

            except asyncio.CancelledError:

                break

            except Exception as e:

                print(
                    f"[TRACK LOOP ERROR] "
                    f"{chat_id}: {e}"
                )

            await asyncio.sleep(
                CHECK_INTERVAL
            )