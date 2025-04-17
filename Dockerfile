FROM python:3.12.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY exporter.py .

# Create directory for metrics files
RUN mkdir -p /metrics

# Environment variables
ENV METRICS_DIR=/metrics
ENV PORT=9090

# Expose the port
EXPOSE 9090

# Run the application
CMD ["python", "exporter.py"]