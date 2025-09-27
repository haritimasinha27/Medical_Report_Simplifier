# Use official Python slim image
FROM python:3.11-slim

# Install system dependencies, including Tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libsm6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy the rest of the project files
COPY . .

# Expose port (Render uses 10000 by default, override if needed)


# Start the Django app using Gunicorn
# CMD ["gunicorn", "medical_simplifier.wsgi:application", "--bind", "0.0.0.0:10000", "--workers", "3"]
# Start Django with Gunicorn — shell form allows $PORT expansion
CMD gunicorn medical_simplifier.wsgi:application --bind 0.0.0.0:$PORT --workers 3



