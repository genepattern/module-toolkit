# GenePattern Module Generator - Dockerfile
# This Dockerfile builds an image for the module generator webapp

FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install system dependencies (including docker CLI for building images)
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files first (for better caching)
COPY requirements.txt /app/requirements.txt
COPY app/requirements.txt /app/app-requirements.txt

# Install Python dependencies from both requirements files
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && pip install --no-cache-dir -r /app/app-requirements.txt

# Copy the application code (excluding .env files via .dockerignore)
COPY . /app

# Remove any .env files that might have been copied
RUN rm -f /app/.env /app/app/.env

# Create the sessions directory for Django
RUN mkdir -p /app/app/sessions

# Create generated-modules directory
RUN mkdir -p /app/generated-modules

# Set the MODULE_TOOLKIT_PATH environment variable for the webapp
ENV MODULE_TOOLKIT_PATH=/app

# Expose port 8000 for the Django development server
EXPOSE 8000

# Set the working directory to the app folder for Django
WORKDIR /app/app

# Run the Django development server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

