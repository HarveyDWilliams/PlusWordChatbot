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
EXPOSE 3000

# Run with gunicorn (WSGI server)
CMD ["gunicorn", "--bind", "0.0.0.0:3000", "pluswordchatbot:app"]
