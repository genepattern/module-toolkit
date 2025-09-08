# This Dockerfile should fail because it tries to copy a non-existent file
FROM alpine:3.19
WORKDIR /app
COPY missing.txt /app/missing.txt
RUN echo "should not reach this step"
