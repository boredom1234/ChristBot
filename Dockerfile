# Use the official Python base image
FROM python:3.11

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Download and install Google Chrome
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -i google-chrome-stable_current_amd64.deb && \
    apt-get -f install -y && \
    rm google-chrome-stable_current_amd64.deb

# Download and install ChromeDriver
RUN LATEST_VERSION=$(wget -qO- https://chromedriver.storage.googleapis.com/LATEST_RELEASE) && \
    wget https://chromedriver.storage.googleapis.com/$LATEST_VERSION/chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip && \
    mv chromedriver /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm chromedriver_linux64.zip

# Set working directory
WORKDIR /app

# Copy requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code into the container
COPY . .

# Command to run the application
CMD ["python", "auto.py"]
