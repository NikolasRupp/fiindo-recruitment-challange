# Use Slim Python Image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install requirements
RUN pip install --no-cache-dir -r requirements.txt

# Copy rest of code
COPY . .

# Run Script
CMD ["python", "-m", "src.main"]