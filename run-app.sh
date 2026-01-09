#!/bin/bash
# Run script for the GenePattern Module Generator container
# This script starts the container with proper Docker socket mounting and volume mappings

set -e

# Default values
GENERATED_MODULES_DIR="${GENERATED_MODULES_DIR:-./generated-modules}"
HOST_PORT="${HOST_PORT:-8000}"
CONTAINER_NAME="${CONTAINER_NAME:-module-toolkit}"
IMAGE_NAME="${IMAGE_NAME:-module-toolkit:latest}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--modules-dir)
            GENERATED_MODULES_DIR="$2"
            shift 2
            ;;
        -p|--port)
            HOST_PORT="$2"
            shift 2
            ;;
        -n|--name)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        -i|--image)
            IMAGE_NAME="$2"
            shift 2
            ;;
        --build)
            BUILD_IMAGE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -d, --modules-dir DIR   Directory to mount for generated modules (default: ./generated-modules)"
            echo "  -p, --port PORT         Host port to map to container port 8000 (default: 8000)"
            echo "  -n, --name NAME         Container name (default: module-toolkit)"
            echo "  -i, --image IMAGE       Docker image name (default: module-toolkit:latest)"
            echo "  --build                 Build the Docker image before running"
            echo "  -h, --help              Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Convert to absolute path
GENERATED_MODULES_DIR=$(cd "$(dirname "$GENERATED_MODULES_DIR")" 2>/dev/null && pwd)/$(basename "$GENERATED_MODULES_DIR") || GENERATED_MODULES_DIR=$(pwd)/generated-modules

# Create the generated-modules directory if it doesn't exist
mkdir -p "$GENERATED_MODULES_DIR"

# Build the image if requested
if [ "$BUILD_IMAGE" = true ]; then
    echo "Building Docker image: $IMAGE_NAME"
    docker build -t "$IMAGE_NAME" -f app.Dockerfile .
fi

# Stop and remove existing container if it exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Stopping and removing existing container: $CONTAINER_NAME"
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
fi

echo "Starting container: $CONTAINER_NAME"
echo "  - Generated modules directory: $GENERATED_MODULES_DIR"
echo "  - Host port: $HOST_PORT"
echo "  - Docker socket mounted for image building"

# Run the container
docker run -d \
    --name "$CONTAINER_NAME" --rm \
    -p "${HOST_PORT}:8000" \
    -v "$GENERATED_MODULES_DIR:/app/generated-modules" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e MODULE_TOOLKIT_PATH=/app \
    --env-file .env \
    --env-file app/.env \
    "$IMAGE_NAME"

echo ""
echo "Container started successfully!"
echo "Access the webapp at: http://localhost:${HOST_PORT}"
echo ""
echo "Useful commands:"
echo "  View logs:     docker logs -f $CONTAINER_NAME"
echo "  Stop:          docker stop $CONTAINER_NAME"
echo "  Remove:        docker rm $CONTAINER_NAME"
