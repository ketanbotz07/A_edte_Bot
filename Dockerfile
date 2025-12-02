# बेस इमेज
FROM python:3.11-slim

# वर्किंग डायरेक्टरी सेट करें
WORKDIR /app

# 1. FFmpeg और अन्य आवश्यक डिपेंडेंसी इंस्टॉल करें
# ⚠️ सुनिश्चित करें कि यह 'ffmpeg' इंस्टॉल करता है ⚠️
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# 2. डिपेंडेंसी कॉपी करें और इंस्टॉल करें
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. एप्लिकेशन कोड कॉपी करें
COPY . .

# 4. कमांड चलाएँ
CMD ["python", "main.py"]
