# बेस इमेज
FROM python:3.11-slim

# वर्किंग डायरेक्टरी सेट करें
WORKDIR /app

# FFmpeg और अन्य आवश्यक डिपेंडेंसी इंस्टॉल करें
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# डिपेंडेंसी कॉपी करें और इंस्टॉल करें
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# एप्लिकेशन कोड कॉपी करें
COPY . .

# कमांड चलाएँ
CMD ["python", "main.py"]
