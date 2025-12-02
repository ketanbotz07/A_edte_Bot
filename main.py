import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
import requests # ⬅️ Mux API कॉल करने के लिए
import json
import base64
import time

# ---------------- CONFIG ----------------
PORT_NUMBER = int(os.environ.get("PORT", 8080))
# Mux API Keys को Environment Variables से लें
MUX_ACCESS_TOKEN_ID = os.environ.get("MUX_ACCESS_TOKEN_ID")
MUX_SECRET_KEY = os.environ.get("MUX_SECRET_KEY")

# Mux API Endpoints
MUX_API_BASE = "https://api.mux.com"

# Pyrogram Client Setup
app = Client(
    "video_editor_bot",
    api_id=os.environ.get("API_ID"),
    api_hash=os.environ.get("API_HASH"),
    bot_token=os.environ.get("BOT_TOKEN")
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

# ------------- GLOBAL LOCK (CPU SAFE) -------------
video_lock = asyncio.Lock()    

# -------------------- MUX HELPER FUNCTIONS --------------------

def get_mux_headers():
    """Mux API के लिए Basic Auth हेडर तैयार करें"""
    if not MUX_ACCESS_TOKEN_ID or not MUX_SECRET_KEY:
        raise ValueError("MUX API Keys are missing in Environment Variables.")
    
    # Basic Auth हेडर बनाने के लिए ID और Key को Base64 में एन्कोड करें
    credentials = f"{MUX_ACCESS_TOKEN_ID}:{MUX_SECRET_KEY}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    return {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/json"
    }

def create_mux_upload_url():
    """Mux से एक नया डायरेक्ट अपलोड URL प्राप्त करें"""
    url = f"{MUX_API_BASE}/video/v1/uploads"
    
    # यह payload Mux को बताता है कि वीडियो अपलोड होने के बाद उसे कैसे प्रोसेस करना है।
    payload = {
        "new_asset_settings": {
            # 'passthrough' का उपयोग आप अपनी पहचान के लिए कर सकते हैं
            "passthrough": f"telegram_user_{time.time()}",
            "playback_policy": ["public"] 
        },
        # Direct Upload टाइप चुनें
        "test": True # टेस्टिंग मोड में रखें (आप इसे हटा सकते हैं जब आप तैयार हों)
    }
    
    headers = get_mux_headers()
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    response.raise_for_status() # HTTP त्रुटि होने पर एक्सेप्शन उठाएँ
    
    data = response.json()['data']
    return data['id'], data['url'] # upload_id और upload_url वापस करें


# -------------------- START CMD --------------------
@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text(
        "नमस्ते! 👋\n\n"
        "🚀 बॉट अब **Mux Cloud** का उपयोग करके वीडियो प्रोसेस करेगा। CPU क्रैश नहीं होगा!\n"
        "मुझे कोई भी वीडियो भेजें।"
    )

# -------------------- VIDEO PROCESS (MUX INTEGRATION) --------------------
@app.on_message(filters.video | filters.document) 
async def process_video(client, message):

    status = await message.reply_text("वीडियो प्राप्त हुआ है… कृपया प्रतीक्षा करें…")
    input_path = None
    
    async with video_lock:
        await status.edit_text("🔄 Mux क्लाउड के लिए प्रोसेसिंग शुरू...")

        try:
            # 1. वीडियो डाउनलोड करें (डिस्क पर)
            await status.edit_text("⬇ वीडियो डाउनलोड हो रहा है (लोकल डिस्क पर)...")
            input_path = await message.download()
            
            # 2. Mux से अपलोड URL प्राप्त करें
            await status.edit_text("🔗 Mux से अपलोड URL प्राप्त किया जा रहा है...")
            upload_id, upload_url = await asyncio.to_thread(create_mux_upload_url)
            
            # 3. Mux पर अपलोड करें (सबसे धीमी प्रक्रिया)
            await status.edit_text("⬆ वीडियो Mux क्लाउड पर अपलोड किया जा रहा है...")
            
            # फ़ाइल को सीधे Mux URL पर भेजें
            with open(input_path, 'rb') as f:
                # Mux डायरेक्ट अपलोड के लिए कोई Content-Type नहीं चाहिए, सिर्फ फाइल भेजें
                upload_response = await asyncio.to_thread(requests.put, upload_url, data=f, headers={})
            
            upload_response.raise_for_status() # यदि अपलोड फेल हो तो एक्सेप्शन उठाएँ

            # 4. स्टेटस अपडेट करें (Mux अब प्रोसेसिंग कर रहा है)
            await status.edit_text(
                "✅ अपलोड सफल! Mux अब वीडियो को प्रोसेस कर रहा है (यह 1-2 मिनट ले सकता है)।"
                "\n\nआपको जल्द ही रिजल्ट मिलेगा। (ID: " + upload_id + ")"
            )
            
            # ⚠️ यहाँ आपको Webhook सेटअप करना होगा ताकि Mux प्रोसेसिंग पूरी होने पर जवाब भेज सके।
            # वर्तमान कोड Webhook के बिना, आपको रिजल्ट Telegram पर तुरंत नहीं भेजेगा।
            
            # 5. अंतिम संदेश
            await status.edit_text(
                f"✅ वीडियो Mux को सफलतापूर्वक भेजा गया। Mux इसकी प्रोसेसिंग शुरू कर चुका है। \
                \n\n**नोट:** रिजल्ट पाने के लिए, हमें एक Webhook सर्वर की आवश्यकता है। यह बॉट अभी Webhook को नहीं सुन रहा है।"
            )


        except ValueError as ve:
            # API Keys न होने पर त्रुटि
            await status.edit_text(f"❌ कॉन्फ़िगरेशन त्रुटि: MUX API Keys नहीं मिले। कृपया Env Vars जाँचें।")
            
        except requests.exceptions.HTTPError as he:
            # Mux से HTTP 4xx/5xx त्रुटि
            error_details = he.response.text[:150]
            await status.edit_text(f"❌ Mux API त्रुटि: HTTP फ़ेलियर। {error_details}")
            
        except Exception as e:
            # अन्य त्रुटियाँ
            error_msg = f"❌ सामान्य त्रुटि: {str(e)[:150]}"
            print(f"GENERAL ERROR: {error_msg}")
            await status.edit_text(error_msg)

        finally:
            # ---------- CLEANUP ----------
            if input_path and os.path.exists(input_path):
                os.remove(input_path)


# -------------------- MAIN --------------------
if __name__ == "__main__":
    # Ensure Keys are present before starting
    try:
        get_mux_headers() 
    except ValueError as e:
        print(f"FATAL ERROR: {e}")
        exit(1)

    threading.Thread(target=start_health_server, daemon=True).start()
    print("Bot Started...")
    app.run()
