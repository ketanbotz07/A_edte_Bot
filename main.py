import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
import ffmpeg # ⬅️ यह लाइन अब सक्रिय (active) है

# --- कॉन्फ़िगरेशन ---
# Koyeb डिफ़ॉल्ट रूप से 8080 या 8000 की अपेक्षा करता है
PORT_NUMBER = int(os.environ.get("PORT", 8080))

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

# --- 💡 Koyeb Health Check फिक्स ---

class HealthCheckHandler(BaseHTTPRequestHandler):
    """एक न्यूनतम हैंडलर जो किसी भी अनुरोध पर 200 OK जवाब देता है।"""
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running.')

def start_health_server():
    """पोर्ट 8080 पर हेल्थ चेक सर्वर शुरू करता है।"""
    try:
        httpd = HTTPServer(('0.0.0.0', PORT_NUMBER), HealthCheckHandler)
        print(f"Health Check server started on port {PORT_NUMBER}")
        httpd.serve_forever()
    except Exception as e:
        # यदि पोर्ट उपयोग में है या कोई अन्य त्रुटि है
        print(f"Error starting health server: {e}")

# --- 🤖 Telegram Bot Logic (वीडियो प्रोसेसिंग जोड़ी गई) ---

@app.on_message(filters.command("start"))
async def start_command(client, message):
    """स्टार्ट कमांड का जवाब देता है।"""
    await message.reply_text("नमस्ते! 👋 मेरा Health Check अब ठीक हो गया है और मैं काम कर रहा हूँ। मुझे वीडियो भेजें!")

@app.on_message(filters.video)
async def process_video(client, message):
    """आने वाले वीडियो को प्रोसेस करता है और 90 डिग्री घुमाता है।"""
    
    # 1. Status Message और Setup
    status_msg = await message.reply_text("वीडियो प्राप्त हुआ। डाउनलोडिंग और प्रोसेसिंग शुरू हो रही है...")
    
    download_path = None
    output_path = None
    
    try:
        # 1.1 डाउनलोड शुरू करें
        download_path = await message.download()
        output_path = f"rotated_{os.path.basename(download_path)}"

        await status_msg.edit_text("वीडियो डाउनलोड हुआ। प्रोसेसिंग (90° घुमाव) शुरू...")
        
        # 2. FFmpeg के साथ प्रोसेसिंग - 'ultrafast' का उपयोग करें
        (
            ffmpeg
            .input(download_path)
            .output(output_path, 
                vcodec='libx264',           # अच्छा कंपैटिबिलिटी
                acodec='aac',               # अच्छा ऑडियो कंपैटिबिलिटी
                vf='transpose=1',           # 90 डिग्री क्लॉकवाइज घुमाना
                preset='ultrafast',         # ⬅️ प्रोसेसिंग को तेज़ करने के लिए
                crf=23                      # क्वालिटी पैरामीटर
            )
            .run(overwrite_output=True)
        )
        
        # 3. Upload
        await status_msg.edit_text("एडिटेड वीडियो अपलोड किया जा रहा है...")
        await client.send_video(
            chat_id=message.chat.id,
            video=output_path,
            caption="✅ आपका 90° घुमाया गया वीडियो!"
        )
        
        await status_msg.delete()

    except Exception as e:
        # ⚠️ त्रुटि को Telegram पर वापस भेजेगा।
        error_trace = f"An error occurred: {e}"
        print(f"VIDEO PROCESSING ERROR: {error_trace}")
        
        await status_msg.edit_text(
            f"❌ वीडियो प्रोसेसिंग में त्रुटि हुई। शायद CPU/मेमोरी की कमी है।\n\nत्रुटि: {str(e)[:150]}"
        )
        
    finally:
        # 4. Cleanup (फाइलें हटाएँ)
        if download_path and os.path.exists(download_path):
            os.remove(download_path)
        if output_path and os.path.exists(output_path):
            os.remove(output_path)

# --- मुख्य निष्पादन (Main Execution) ---

if __name__ == "__main__":
    
    # 1. Health Check सर्वर को एक अलग थ्रेड में शुरू करें
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    
    # 2. मुख्य थ्रेड में Telegram Bot को शुरू करें
    print("Telegram Bot शुरू हो रहा है...")
    app.run()
