# Dockerfile for SmartShelf Intelligent Library Management System
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV PORT=5000

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Ensure instance directory exists
RUN mkdir -p instance

# Initialize and seed database if not present
RUN python seed.py

EXPOSE 5000

# Run with Waitress WSGI production server
CMD ["python", "wsgi.py"]
