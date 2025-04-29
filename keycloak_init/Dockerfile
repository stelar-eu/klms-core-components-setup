FROM python:3.13

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY ./requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt

# Install the MinIO client
RUN wget https://dl.min.io/client/mc/release/linux-amd64/mc \
    && chmod +x mc \
    && mv mc /usr/local/bin/

# Copy the rest of the application files
COPY . /app/

# Set the PYTHONPATH (modify as needed)
ENV PYTHONPATH=/app/src

# Run the application
CMD ["python3", "run.py"]

