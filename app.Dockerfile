# GenePattern Module Generator - Dockerfile
# This Dockerfile builds an image for the module generator webapp

FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install system dependencies and Docker CLI (version 20.10 to match host daemon API 1.41)
# Download Docker CLI binary directly since package repos don't have older versions
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-20.10.24.tgz -o docker.tgz \
    && tar -xzf docker.tgz --strip-components=1 -C /usr/local/bin docker/docker \
    && rm docker.tgz \
    && chmod +x /usr/local/bin/docker

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

# Expose port 8250 for the Django development server
EXPOSE 8250

# Set the working directory to the app folder for Django
WORKDIR /app/app

# Run the Django development server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8250"]
