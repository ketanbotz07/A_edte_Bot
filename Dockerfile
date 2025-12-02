# बेस इमेज
FROM python:3.11-slim

# वर्किंग डायरेक्टरी सेट करें
WORKDIR /app

# 1. कोई FFmpeg इंस्टॉलेशन नहीं, सिर्फ़ apt अपडेट
RUN apt-get update && \
    rm -rf /var/lib/apt/lists/*

# 2. डिपेंडेंसी कॉपी करें और इंस्टॉल करें
# (requests लाइब्रेरी यहां इंस्टॉल हो जाएगी)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. एप्लिकेशन कोड कॉपी करें
COPY . .

# 4. कमांड चलाएँ
CMD ["python", "main.py"]
