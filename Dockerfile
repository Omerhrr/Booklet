# Dockerfile for Render Deployment

# 1. Start with a modern, stable Python base image
FROM python:3.11-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Install system-level dependencies
# This is where we solve the WeasyPrint problem permanently.
# We install all necessary libraries for PDF generation and graphics.
RUN apt-get update && apt-get install -y \
    build-essential \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 4. Copy the requirements file first to leverage Docker's layer caching
COPY requirements.txt .

# 5. Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy the rest of your application code into the container
COPY . .

# 7. Expose the port the application will run on
EXPOSE 8000

# 8. Define the command to run your application using Gunicorn
# Gunicorn is a production-ready web server for Python.
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "--bind", "0.0.0.0:8000"]
