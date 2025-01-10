import os
import re
import uuid
import time
import logging
import asyncio
import aiohttp
from pyrogram.enums import ParseMode
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from plugins.utils import (
    async_download_file,
    get_file_size, 
    file_size_format,
    get_filename,
    progressArgs
)

from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    SESSION_STRING,
    MAX_FILE_SIZE,
    DOWNLOAD_LOCATION,
    OWNER_ID
)

bot = Client(
    "uploader_bot", 
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=1000,
    parse_mode=ParseMode.MARKDOWN
)

user = Client(
    "user_session",
    workers=1000,
    session_string=SESSION_STRING
)

pending_renames = {}
pending_downloads = {}

URL_REGEX = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
YOUTUBE_REGEX = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/.+'

THUMB_LOCATION = "./THUMBNAILS"

# Create required directories
os.makedirs(DOWNLOAD_LOCATION, exist_ok=True)
os.makedirs(THUMB_LOCATION, exist_ok=True)

async def get_max_file_size(user_id: int) -> int:
    return MAX_FILE_SIZE

async def get_concurrent_downloads(user_id: int) -> int:
    return 5

async def save_thumb(user_id: int, thumb_path: str):
    """Save user's thumbnail"""
    os.makedirs(os.path.join(THUMB_LOCATION, str(user_id)), exist_ok=True)
    thumb_file = os.path.join(THUMB_LOCATION, str(user_id), "thumbnail.jpg")
    try:
        # Copy and convert thumbnail
        from PIL import Image
        image = Image.open(thumb_path)
        image.convert("RGB").save(thumb_file, "JPEG")
        return thumb_file
    except Exception as e:
        logging.error(f"Error saving thumbnail: {str(e)}")
        return None

def get_thumb(user_id: int):
    """Get user's saved thumbnail"""
    thumb_file = os.path.join(THUMB_LOCATION, str(user_id), "thumbnail.jpg")
    if os.path.exists(thumb_file):
        return thumb_file
    return None

def delete_thumb(user_id: int):
    """Delete user's saved thumbnail"""
    thumb_file = os.path.join(THUMB_LOCATION, str(user_id), "thumbnail.jpg")
    try:
        if os.path.exists(thumb_file):
            os.remove(thumb_file)
            return True
    except Exception as e:
        logging.error(f"Error deleting thumbnail: {str(e)}")
    return False

START_TEXT = """
✨ **Welcome to URL Uploader Bot** ✨

I can help you download files from direct links and upload them to Telegram.

**Features:**
• 📥 Upload files up to 4GB
• 🎥 Support for YouTube links
• ⚡️ Fast downloads
• 📝 Custom file renaming
• 📊 Real-time progress tracking

**Commands:**
• /start - Start the bot
• /help - Get detailed help
• /about - About the bot

🔰 Send me any direct download link or YouTube link to get started!
"""

HELP_TEXT = """
📚 **URL Uploader Help**

**How to use:**
1. Send me any direct download link or YouTube link
2. Choose download options:
   • ⚡️ Quick Download - Original filename
   • ✏️ Custom Name - Rename before upload
   • ❌ Cancel - Cancel the process

**Supported Links:**
• Direct download URLs (Up to 4GB)
• YouTube video links
• Google Drive links (soon)

**Features:**
• 🚀 Fast processing
• 📊 Progress updates
• 🎯 Error reporting
• 💫 Beautiful interface

Need help? Contact @{OWNER_ID}
"""

ABOUT_TEXT = """
✨ **URL Uploader Bot**

**Version:** 2.0
**Last Updated:** 2025

🛠 **Developed with:**
• Python 3.9
• Pyrogram 2.0

📊 **Server Status:**
• Online: ✅
• Processing Speed: ⚡️
• Server Load: Optimal

Thanks for using our Bot!

©️ 2025 All Rights Reserved
"""

# Command handlers
@bot.on_message(filters.command(["start"]) & filters.private)
async def start_command(client, message: Message):
    chat_id = message.chat.id
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✨ Help", callback_data="help"),
            InlineKeyboardButton("📊 About", callback_data="about")
        ],
        [
            InlineKeyboardButton("🌟 Channel", url="https://t.me/your_channel"),
            InlineKeyboardButton("💫 Support", url="https://t.me/your_support")
        ]
    ])
    
    await message.reply_text(
        START_TEXT,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

@bot.on_message(filters.command(["help"]) & filters.private)
async def help_command(client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏠 Back to Start", callback_data="start"),
            InlineKeyboardButton("📊 About", callback_data="about")
        ]
    ])
    
    await message.reply_text(
        HELP_TEXT,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

@bot.on_message(filters.command(["about"]) & filters.private)
async def about_command(client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏠 Back to Start", callback_data="start"),
            InlineKeyboardButton("❓ Help", callback_data="help")
        ]
    ])
    
    await message.reply_text(
        ABOUT_TEXT,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

# Callback query handler for inline buttons
@bot.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    
    if data == "start":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✨ Help", callback_data="help"),
                InlineKeyboardButton("📊 About", callback_data="about")
            ],
            [
                InlineKeyboardButton("🌟 Channel", url="https://t.me/your_channel"),
                InlineKeyboardButton("💫 Support", url="https://t.me/your_support")
            ]
        ])
        
        await callback_query.message.edit_text(
            START_TEXT,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    
    elif data == "help":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🏠 Back to Start", callback_data="start"),
                InlineKeyboardButton("📊 About", callback_data="about")
            ]
        ])
        
        await callback_query.message.edit_text(
            HELP_TEXT,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    
    elif data == "about":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🏠 Back to Start", callback_data="start"),
                InlineKeyboardButton("❓ Help", callback_data="help")
            ]
        ])
        
        await callback_query.message.edit_text(
            ABOUT_TEXT,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    
    elif "|" in data:
        # Handle file download/rename callbacks
        action, unique_id = data.split("|")
        
        if action == "cancel":
            if unique_id in pending_downloads:
                pending_downloads.pop(unique_id)
            await callback_query.message.edit_text(
                "**❌ Download Cancelled**\n\n"
                "Send another URL to start a new download."
            )
            return
        
        # Get URL from stored data
        download_info = pending_downloads.get(unique_id)
        if not download_info:
            await callback_query.message.edit_text(
                "**❌ Error: Download information not found**\n\n"
                "Please send the URL again."
            )
            return
        
        url = download_info["url"]
        
        try:
            processing_msg = await callback_query.message.edit_text(
                "**🔄 Processing Request**\n\n"
                "⚡️ Initializing download...\n"
                "📊 Preparing file information..."
            )
            
            file_size_bytes = await get_file_size(url)
            file_size_readable = file_size_format(file_size_bytes)
            
            if file_size_bytes > MAX_FILE_SIZE:
                await processing_msg.edit_text(
                    "**❌ File Too Large**\n\n"
                    "Maximum file size limit: 4GB\n"
                    f"Detected file size: {file_size_readable}\n\n"
                    "Please try with a smaller file."
                )
                pending_downloads.pop(unique_id)
                return
            
            if action == "default":
                # Download with original filename
                filename = await get_filename(url)
                start_time = time.time()
                editable_text = await client.send_message(
                    chat_id=chat_id,
                    text="📥 Starting Download..."
                )
                
                downloaded_file = await async_download_file(
                    url,
                    filename,
                    progress=progress_for_pyrogram,
                    progress_args=progressArgs("📥 Downloading Progress", editable_text, start_time)
                )
                
                upload_start_time = time.time()
                await send_file_with_thumbnail(
                    client,
                    chat_id,
                    downloaded_file,
                    filename,
                    f"📤 **Upload Complete!**\n\n**Filename:** `{filename}`",
                    progress_for_pyrogram,
                    progressArgs("📤 Uploading Progress", editable_text, upload_start_time)
                )
                
                await editable_text.delete()
                await processing_msg.delete()
                os.remove(downloaded_file)
                pending_downloads.pop(unique_id)
            
            elif action == "rename":
                # Store URL for rename
                pending_renames[chat_id] = url
                pending_downloads.pop(unique_id)
                
                # Get original filename
                original_filename = await get_filename(url)
                
                await processing_msg.edit_text(
                    "**✏️ Send me the new filename**\n\n"
                    f"**Original filename:** `{original_filename}`\n\n"
                    "• Send the new name without extension\n"
                    "• Extension will be added automatically\n"
                    "• Send /cancel to cancel the process"
                )
        
        except Exception as e:
            if unique_id in pending_downloads:
                pending_downloads.pop(unique_id)
            await processing_msg.edit_text(
                f"**❌ Error occurred:**\n\n`{str(e)}`"
            )
    
    # Answer the callback query
    await callback_query.answer()

# Handle text messages (URLs and rename requests)
@bot.on_message(filters.text & filters.private & ~filters.command("start") & ~filters.command("help") & ~filters.command("about"))
async def handle_message(client, message: Message):
    text = message.text.strip()
    chat_id = message.chat.id
    
    # Check if this is a rename request
    if chat_id in pending_renames:
        if text.lower() == "/cancel":
            pending_renames.pop(chat_id)
            await message.reply_text("❌ Process Cancelled")
            return
        
        # Process rename request
        try:
            url = pending_renames[chat_id]
            new_name = text
            
            # Get original file extension
            original_filename = await get_filename(url)
            _, ext = os.path.splitext(original_filename)
            
            # Add extension if not provided
            if not ext:
                ext = ".mp4"  # Default extension
            if not new_name.endswith(ext):
                new_name_with_ext = f"{new_name}{ext}"
            else:
                new_name_with_ext = new_name
            
            # Start download process
            start_time = time.time()
            status_msg = await message.reply_text(
                "**🔄 Processing Download**\n\n"
                f"**New filename:** `{new_name_with_ext}`\n"
                "**Status:** Downloading..."
            )
            
            downloaded_file = await async_download_file(
                url,
                new_name_with_ext,
                progress=progress_for_pyrogram,
                progress_args=progressArgs("📥 Downloading Progress", status_msg, start_time)
            )
            
            # Start upload process
            upload_start_time = time.time()
            await send_file_with_thumbnail(
                client,
                chat_id,
                downloaded_file,
                new_name_with_ext,
                f"📤 **Upload Complete!**\n\n**Filename:** `{new_name_with_ext}`",
                progress_for_pyrogram,
                progressArgs("📤 Uploading Progress", status_msg, upload_start_time)
            )
            
            # Cleanup
            await status_msg.delete()
            os.remove(downloaded_file)
            pending_renames.pop(chat_id)
            
        except Exception as e:
            error_msg = f"**❌ Error occurred:**\n\n`{str(e)}`"
            await message.reply_text(error_msg)
            if chat_id in pending_renames:
                pending_renames.pop(chat_id)
        return
    
    # Handle URL
    if re.match(URL_REGEX, text):
        unique_id = str(uuid.uuid4())
        # Store URL for later use
        pending_downloads[unique_id] = {
            "url": text,
            "message_id": message.id,
            "chat_id": chat_id
        }
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚡️ Quick Download", callback_data=f"default|{unique_id}"),
                InlineKeyboardButton("✏️ Custom Name", callback_data=f"rename|{unique_id}")
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{unique_id}")
            ]
        ])
        
        try:
            file_size = await get_file_size(text)
            size_text = file_size_format(file_size)
            original_filename = await get_filename(text)
            
            await message.reply_text(
                f"**🔗 URL Detected!**\n\n"
                f"📦 **File Size:** {size_text}\n"
                f"📄 **Original Name:** `{original_filename}`\n"
                f"🎯 **Choose an option:**",
                reply_markup=keyboard
            )
        except Exception as e:
            await message.reply_text(
                "❌ **Error!**\n\n"
                "Unable to fetch file information.\n"
                "Please check if the URL is valid.",
                quote=True
            )
            if unique_id in pending_downloads:
                pending_downloads.pop(unique_id)

async def progress_text(current, total, start_time):
    now = time.time()
    diff = now - start_time
    
    if diff < 1:
        return ""
    
    speed = current / diff
    speed_text = file_size_format(speed) + "/s"
    
    percentage = (current * 100) / total
    
    bar_length = 10
    current_bar = int(percentage / (100 / bar_length))
    bar = "▰" * current_bar + "▱" * (bar_length - current_bar)
    
    text = (
        f"**📊 Progress Status**\n\n"
        f"**{bar}** `{percentage:.1f}%`\n\n"
        f"**⚡️ Speed:** {speed_text}\n"
        f"**📦 Size:** {file_size_format(current)} / {file_size_format(total)}\n"
    )
    
    return text

def progress_for_pyrogram(current, total):
    return progress_text(current, total, time.time())

@bot.on_message(filters.photo & filters.incoming & filters.private)
async def save_photo(client, message):
    download_location = f"{DOWNLOAD_LOCATION}/{message.from_user.id}.jpg"
    await message.download(file_name=download_location)
    await message.reply_text(text="Your custom thumbnail is saved", quote=True)

@bot.on_message(filters.command("thumb") & filters.incoming & filters.private)
async def handle_thumb_command(client, message: Message):
    user_id = message.from_user.id
    
    if message.reply_to_message and message.reply_to_message.photo:
        # User replied to a photo with the command
        try:
            progress_msg = await message.reply_text("**🔄 Processing thumbnail...**")
            
            # Download the photo
            thumb_path = await message.reply_to_message.download()
            
            # Save the thumbnail
            saved_thumb = await save_thumb(user_id, thumb_path)
            
            # Clean up downloaded file
            os.remove(thumb_path)
            
            if saved_thumb:
                await progress_msg.edit_text(
                    "**✅ Custom thumbnail saved successfully!**\n\n"
                    "This thumbnail will be used for all your uploads.\n"
                    "• Use /delthumb to remove it\n"
                    "• Send /thumb again with another photo to change it"
                )
            else:
                await progress_msg.edit_text("**❌ Failed to save thumbnail**")
        except Exception as e:
            await message.reply_text(f"**❌ Error:** `{str(e)}`")
    else:
        # Check if user has a thumbnail
        thumb_file = get_thumb(user_id)
        if thumb_file:
            try:
                await message.reply_photo(
                    photo=thumb_file,
                    caption="**🖼️ Your current thumbnail**\n\n"
                            "• Reply to a photo with /thumb to change it\n"
                            "• Use /delthumb to remove it"
                )
            except Exception as e:
                await message.reply_text("**❌ Error showing thumbnail**")
        else:
            await message.reply_text(
                "**🖼️ No thumbnail set**\n\n"
                "• Reply to a photo with /thumb to set it\n"
                "• The thumbnail will be used for all your uploads"
            )

@bot.on_message(filters.command("delthumb") & filters.incoming & filters.private)
async def handle_delthumb_command(client, message: Message):
    user_id = message.from_user.id
    
    if delete_thumb(user_id):
        await message.reply_text("**✅ Custom thumbnail deleted successfully!**")
    else:
        await message.reply_text("**❌ No thumbnail found to delete**")

async def send_file_with_thumbnail(client, chat_id, document, file_name, caption, progress, progress_args):
    """Send file with user's thumbnail if available"""
    thumb = get_thumb(chat_id)
    try:
        await client.send_document(
            chat_id=chat_id,
            document=document,
            thumb=thumb,
            file_name=file_name,
            caption=caption,
            progress=progress,
            progress_args=progress_args
        )
    except Exception as e:
        # If sending with thumbnail fails, try without it
        await client.send_document(
            chat_id=chat_id,
            document=document,
            file_name=file_name,
            caption=caption,
            progress=progress,
            progress_args=progress_args
        )

@bot.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_message(client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("Please reply to a message to broadcast.")
        return

    broadcast_text = message.reply_to_message.text
    if not broadcast_text:
        await message.reply_text("The replied message does not contain any text.")
        return

    try:
        await client.send_message(chat_id=OWNER_ID, text=broadcast_text)
        await message.reply_text("✅ Broadcast message sent successfully!")
    except Exception as e:
        await message.reply_text(f"❌ Failed to send broadcast: {str(e)}")

if __name__ == "__main__":
    user.start()
    bot.run()
