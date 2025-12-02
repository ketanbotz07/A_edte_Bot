import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
import ffmpeg
import subprocess # FFmpeg को सीधे चलाने के लिए

# ---------------- CONFIG ----------------
PORT_NUMBER = int(os.environ.get("PORT", 8080))
FILE_SIZE_LIMIT = 10 * 1024 * 1024  # ⬅️ 10 MB की साइज़ लिमिट

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
# सुनिश्चित करें कि एक समय में केवल 1 FFmpeg प्रोसेस चले
video_lock = asyncio.Lock()    


# -------------------- START CMD --------------------
@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text(
        "नमस्ते! 👋\n\n"
        "⚠️ CPU-safe mode में चल रहा है। मैं केवल **10 MB** से छोटी फ़ाइलों को प्रोसेस कर सकता हूँ।\n"
        "मुझे 10 MB से छोटा वीडियो भेजें।"
    )

# -------------------- VIDEO PROCESS (SINGLE FUNCTION) --------------------
@app.on_message(filters.video | filters.document) # वीडियो या डॉक्यूमेंट को प्रोसेस करें
async def process_video(client, message):

    # 1. फ़ाइल साइज़ चेक (सबसे पहले)
    file = message.video or message.document
    
    if file and file.file_size > FILE_SIZE_LIMIT:
        print(f"--- FILE TOO LARGE: {round(file.file_size / (1024*1024))} MB ---")
        await message.reply_text(
            f"❌ यह फ़ाइल बहुत बड़ी है ({round(file.file_size / (1024*1024))} MB)। \
            फ़्री टियर की मेमोरी सीमा के कारण मैं केवल 10 MB से छोटी फ़ाइलों को ही प्रोसेस कर सकता हूँ।"
        )
        return # अगर बड़ा है तो यहीं रुक जाएँ

    # अगर साइज़ ठीक है, तो प्रोसेसिंग शुरू करें
    status = await message.reply_text("वीडियो प्राप्त हुआ है… कृपया प्रतीक्षा करें…")
    
    input_path = None
    output_path = None

    async with video_lock:       # --------- QUEUE SYSTEM -------------
        await status.edit_text("🔄 Encoding queue में आपका नंबर आ गया है…")

        try:
            # -------- Download --------
            await status.edit_text("⬇ वीडियो डाउनलोड हो रहा है…")
            input_path = await message.download()
            output_path = f"rotated_{os.path.basename(input_path)}"

            # -------- Process (CPU/Memory Optimized FFmpeg) --------
            await status.edit_text("⚙ प्रोसेसिंग शुरू… (Optimized Mode)")

            # FFmpeg को सीधे subprocess से चलाएं (जो कभी-कभी ffmpeg-python से बेहतर होता है)
            command = [
                'ffmpeg',
                '-i', input_path,
                '-vf', 'transpose=1', # 90 डिग्री घुमाने का कमांड
                '-c:v', 'libx264',    # वीडियो कोडेक
                '-preset', 'ultrafast', # सबसे तेज एनकोडिंग
                '-crf', '28',         # क्वालिटी थोड़ी कम करें, साइज़ कम करें
                '-threads', '1',      # 1 CPU कोर का उपयोग करें
                output_path
            ]
            
            # subprocess से चलाएँ और त्रुटि की जाँच करें
            subprocess.run(command, check=True, capture_output=True)


            # -------- Upload --------
            await status.edit_text("⬆ वीडियो अपलोड किया जा रहा है…")

            await client.send_video(
                chat_id=message.chat.id,
                video=output_path,
                caption="✅ आपका 90° घुमाया गया वीडियो तैयार है!",
            )

            await status.delete()

        except subprocess.CalledProcessError as e:
            # FFmpeg कमांड फ़ेल होने पर त्रुटि
            error_msg = f"❌ FFmpeg त्रुटि: {e.stderr.decode()[:150]}"
            print(f"FFMPEG ERROR: {error_msg}")
            await status.edit_text(error_msg)
            
        except Exception as e:
            # अन्य सभी त्रुटियाँ (जैसे मेमोरी, डाउनलोडिंग)
            error_msg = f"❌ प्रोसेसिंग में सामान्य त्रुटि: {str(e)[:150]}"
            print(f"GENERAL ERROR: {error_msg}")
            await status.edit_text(error_msg)

        finally:
            # ---------- CLEANUP ----------
            try:
                # सुनिश्चित करें कि फ़ाइलें मौजूद हों तभी हटें
                if input_path and os.path.exists(input_path):
                    os.remove(input_path)
                if output_path and os.path.exists(output_path):
                    os.remove(output_path)
            except Exception as e:
                print(f"Cleanup failed: {e}")


# -------------------- MAIN --------------------
if __name__ == "__main__":
    threading.Thread(target=start_health_server, daemon=True).start()
    print("Bot Started...")
    app.run()
