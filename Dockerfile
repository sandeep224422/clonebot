FROM nikolaik/python-nodejs:python3.10-nodejs19

# 🔧 Replace expired Debian buster repos with archived ones
RUN sed -i 's|deb.debian.org|archive.debian.org|g' /etc/apt/sources.list \
 && sed -i '/security.debian.org/d' /etc/apt/sources.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# 📦 Copy your project files
COPY . /app/
WORKDIR /app/

# 📌 Install Python dependencies
RUN pip3 install --no-cache-dir --upgrade pip \
 && pip3 install --no-cache-dir --upgrade -r requirements.txt

# ▶️ Start the bot
CMD ["bash", "start"]
