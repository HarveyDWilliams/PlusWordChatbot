# Use a slim Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required by OpenCV and cron
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    libtesseract-dev \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Add cron job: run schedule_reminders.py every minute
RUN echo "* * * * * /usr/local/bin/python /app/schedule_reminders.py >> /var/log/cron.log 2>&1" \
    > /etc/cron.d/schedule_reminders \
    && chmod 0644 /etc/cron.d/schedule_reminders \
    && crontab /etc/cron.d/schedule_reminders

# Expose the port your app will run on
EXPOSE 8000

# Start cron and Gunicorn together
CMD service cron start && gunicorn --bind 0.0.0.0:8000 wsgi:app
