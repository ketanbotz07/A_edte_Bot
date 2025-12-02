import os
import asyncio
from pyrogram import Client, filters
import ffmpeg

# --- कॉन्फ़िगरेशन ---
# ये वेरिएबल Koyeb Environment Variables से आएंगे
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Pyrogram क्लाइंट शुरू करें
app = Client(
    "video_editor_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.command("start"))
async def start_command(client, message):
    """स्टार्ट कमांड का जवाब देता है।"""
    await message.reply_text("नमस्ते! 👋 मुझे कोई वीडियो भेजें, मैं उसे 90 डिग्री घुमाकर (Rotate) वापस भेजूंगा।")

@app.on_message(filters.video)
async def process_video(client, message):
    """आने वाले वीडियो को प्रोसेस करता है और 90 डिग्री घुमाता है।"""
    
    # 1. वीडियो डाउनलोड करें
    status_msg = await message.reply_text("वीडियो प्राप्त हुआ। प्रोसेसिंग शुरू हो रही है...")
    
    download_path = await message.download()
    output_path = f"rotated_{os.path.basename(download_path)}"
    
    try:
        await status_msg.edit_text("वीडियो को 90° घुमाया जा रहा है (FFmpeg)...")
        
        # 2. FFmpeg के साथ प्रोसेसिंग (90 डिग्री घुमाएँ)
        # transpose=1 का मतलब है 90 डिग्री क्लॉकवाइज घुमाना
        (
            ffmpeg
            .input(download_path)
            .output(output_path, vcodec='libx264', acodec='aac', vf='transpose=1', preset='fast')
            .run(overwrite_output=True)
        )
        
        # 3. एडिटेड वीडियो वापस अपलोड करें
        await status_msg.edit_text("एडिटेड वीडियो अपलोड किया जा रहा है...")
        await client.send_video(
            chat_id=message.chat.id,
            video=output_path,
            caption="✅ आपका 90° घुमाया गया वीडियो!"
        )
        
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ त्रुटि हुई: {e}")
    
    finally:
        # 4. अस्थायी फाइलें हटाएँ
        os.remove(download_path)
        if os.path.exists(output_path):
            os.remove(output_path)

if __name__ == "__main__":
    print("बॉट शुरू हो रहा है...")
    app.run()
