# Start with alpine
FROM alpine:3.19.1

# Add the wait4x utility
RUN apk add wait4x

# Add the script to build the URL
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Use the script as the entrypoint
ENTRYPOINT ["/entrypoint.sh"]