# Use a slim Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port your app will run on
EXPOSE 8000

# Run with gunicorn (WSGI server)
# Replace 'pluswordchatbot:app' with your actual module:app name
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "pluswordchatbot:app"]
