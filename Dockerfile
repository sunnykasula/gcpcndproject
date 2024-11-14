# Use an official Python image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app code
COPY . /app/

# Expose port 8080
EXPOSE 8080

# Run the Flask app
CMD ["python", "app.py"]
