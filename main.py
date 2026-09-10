import asyncio
import logging

from pyrogram import (
    Client,
    filters,
    idle
)

from pyrogram.raw import types

from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    SESSION_STRING,
    LOG_CHANNEL
)

from tracker import VCTracker


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"
    )
)

logger = logging.getLogger(
    "VC-TRACKER"
)


# ==========================================
# BOT
# ==========================================

bot = Client(
    "vc_tracker_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# ==========================================
# USER ACCOUNT
# ==========================================

user = Client(
    "vc_tracker_user",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)


# ==========================================
# LOG CHANNEL
# ==========================================

async def send_log(text):

    try:

        await bot.send_message(
            LOG_CHANNEL,
            text
        )

    except Exception as e:

        logger.error(
            f"LOG CHANNEL ERROR: {e}"
        )


# ==========================================
# TRACKER
# ==========================================

tracker = VCTracker(
    user,
    send_log
)


# ==========================================
# BOT /START
# ==========================================

@bot.on_message(
    filters.command("start")
)
async def start_handler(
    client,
    message
):

    await message.reply_text(
        "🎧 <b>VC Tracker</b>\n\n"
        "✅ Bot is online.\n"
        "🎙️ VC tracking is active."
    )


# ==========================================
# RAW TELEGRAM UPDATES
# ==========================================

@user.on_raw_update()
async def raw_update(
    client,
    update,
    users,
    chats
):

    try:

        # ----------------------------------
        # VC CREATED / UPDATED
        # ----------------------------------

        if isinstance(
            update,
            types.UpdateGroupCall
        ):

            call = update.call

            # Group / channel peer
            peer = getattr(
                update,
                "peer",
                None
            )

            if isinstance(
                peer,
                types.PeerChat
            ):

                chat_id = peer.chat_id

            elif isinstance(
                peer,
                types.PeerChannel
            ):

                chat_id = -1000000000000 - peer.channel_id

            else:

                return

            # Register active call
            await tracker.register_call(
                chat_id,
                call
            )

            # If call ended
            if isinstance(
                call,
                types.GroupCallDiscarded
            ):

                await tracker.call_ended(
                    call
                )

            return

        # ----------------------------------
        # PARTICIPANT UPDATE
        # ----------------------------------

        if isinstance(
            update,
            types.UpdateGroupCallParticipants
        ):

            call = update.call

            # Make sure call is known
            call_id = getattr(
                call,
                "id",
                None
            )

            if (
                call_id
                not in tracker.call_map
            ):

                logger.warning(
                    "Participant update "
                    "received for unknown VC"
                )

                return

            for participant in (
                update.participants
            ):

                await tracker.handle_participant(
                    call,
                    participant,
                    users
                )

            return

    except Exception as e:

        logger.exception(
            f"RAW UPDATE ERROR: {e}"
        )


# ==========================================
# START
# ==========================================

async def main():

    logger.info(
        "Starting VC Tracker..."
    )

    # Start bot
    await bot.start()

    bot_me = await bot.get_me()

    logger.info(
        f"Bot started: "
        f"@{bot_me.username}"
    )

    # Start user session
    await user.start()

    user_me = await user.get_me()

    logger.info(
        f"User session started: "
        f"{user_me.first_name} "
        f"(ID: {user_me.id})"
    )

    logger.info(
        "VC tracker is ready."
    )

    await idle()

    await bot.stop()
    await user.stop()


if __name__ == "__main__":

    asyncio.run(
        main()
    )