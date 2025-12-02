import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
import ffmpeg

# ---------------- CONFIG ----------------
PORT_NUMBER = int(os.environ.get("PORT", 8080))

API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

app = Client(
    "video_editor_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ------------ HEALTH CHECK SERVER ------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running")

def start_health_server():
    try:
        httpd = HTTPServer(("0.0.0.0", PORT_NUMBER), HealthCheckHandler)
        print(f"Health Check server started on {PORT_NUMBER}")
        httpd.serve_forever()
    except Exception as e:
        print(f"Health Server Error: {e}")


# ------------- GLOBAL VIDEO QUEUE (CPU SAFE) -------------
video_lock = asyncio.Lock()    # ensure only 1 FFmpeg process at a time


# -------------------- START CMD --------------------
@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text(
        "नमस्ते! 👋\n\n"
        "⚡ अब बॉट CPU-safe mode में चल रहा है.\n"
        "मुझे कोई भी वीडियो भेजें – मैं उसे 90° घुमाकर वापस भेज दूंगा!"
    )

# -------------------- VIDEO PROCESS --------------------
# process_video फ़ंक्शन के अंदर:
@app.on_message(filters.video | filters.document) 
async def process_video(client, message):
    
    # 10 MB की लिमिट सेट करें (फ्री टियर के लिए सुरक्षित)
    file_size_limit = 10 * 1024 * 1024 
    file = message.video or message.document
    
    if file and file.file_size > file_size_limit:
        # अगर साइज़ ज़्यादा है, तो जवाब दें और फंक्शन रोक दें
        print(f"--- FILE TOO LARGE: {round(file.file_size / (1024*1024))} MB ---")
        await message.reply_text(
            f"❌ यह फ़ाइल बहुत बड़ी है ({round(file.file_size / (1024*1024))} MB)। \
            फ़्री टियर की मेमोरी सीमा के कारण मैं केवल 10 MB से छोटी फ़ाइलों को ही प्रोसेस कर सकता हूँ।"
        )
        return # यहीं पर फंक्शन को रोक दें
        
    print(f"--- VIDEO RECEIVED... ---")
    # ... बाकी प्रोसेसिंग कोड यहाँ जारी रहेगा

@app.on_message(filters.video)
async def process_video(client, message):

    status = await message.reply_text("वीडियो प्राप्त हुआ है… कृपया प्रतीक्षा करें…")

    async with video_lock:       # --------- QUEUE SYSTEM -------------
        await status.edit_text("🔄 Encoding queue में आपका नंबर आ गया है…")

        try:
            # -------- Download --------
            await status.edit_text("⬇ वीडियो डाउनलोड हो रहा है…")
            input_path = await message.download()
            output_path = f"rotated_{os.path.basename(input_path)}"

            # -------- Process (Low CPU FFmpeg) --------
            await status.edit_text("⚙ प्रोसेसिंग शुरू… (Low-CPU Mode)")

            (
                ffmpeg
                .input(input_path)
                .output(
                    output_path,
                    vcodec="libx264",
                    acodec="aac",
                    vf="transpose=1",
                    preset="veryslow",   # ✔ CPU low
                    crf=28,              # ✔ more compression
                    threads=1            # ✔ only 1 CPU core
                )
                .run(overwrite_output=True)
            )

            # -------- Upload --------
            await status.edit_text("⬆ वीडियो अपलोड किया जा रहा है…")

            await client.send_video(
                chat_id=message.chat.id,
                video=output_path,
                caption="✅ आपका 90° घुमाया गया वीडियो तैयार है!",
            )

            await status.delete()

        except Exception as e:
            await status.edit_text(f"❌ प्रोसेसिंग में त्रुटि: {str(e)[:150]}")

        finally:
            # ---------- CLEANUP ----------
            try:
                if os.path.exists(input_path):
                    os.remove(input_path)
                if os.path.exists(output_path):
                    os.remove(output_path)
            except:
                pass


# -------------------- MAIN --------------------
if __name__ == "__main__":
    threading.Thread(target=start_health_server, daemon=True).start()
    print("Bot Started...")
    app.run()
