FROM python:3.11-slim

# Cloud Run environment
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source code
COPY . .

# Create directories
RUN mkdir -p logs data

# Expose port
EXPOSE 8080

# Run bot with health check server
CMD python health_check.py & python main_bot.py
