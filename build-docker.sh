#!/bin/bash
# BabyClaw Docker Image Build Script
# Builds both slim and full versions

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
IMAGE_NAME="${IMAGE_NAME:-babyclaw}"
REGISTRY="${REGISTRY:-agentscope}"
VERSION="${VERSION:-latest}"

echo "========================================"
echo "BabyClaw Docker Build Script"
echo "========================================"
echo "Image Name: $IMAGE_NAME"
echo "Version: $VERSION"
echo ""

# Function to build a version
build_version() {
    local variant=$1
    local include_browser=$2

    echo "========================================"
    echo "Building $variant version..."
    echo "========================================"

    local tag="${REGISTRY}/${IMAGE_NAME}:${VERSION}"
    if [ "$variant" != "latest" ]; then
        tag="${REGISTRY}/${IMAGE_NAME}:${VERSION}-${variant}"
    fi

    echo "Tag: $tag"
    echo "Include Browser: $include_browser"
    echo ""

    docker build \
        --build-arg "INCLUDE_BROWSER=${include_browser}" \
        --tag "$tag" \
        --file deploy/Dockerfile \
        .

    echo ""
    echo "✓ Built $variant version: $tag"
    echo ""

    # Show image size
    echo "Image size:"
    docker images "$IMAGE_NAME" --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}" | grep "$VERSION"
    echo ""
}

# Parse command line arguments
BUILD_SLIM=true
BUILD_FULL=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --slim-only)
            BUILD_FULL=false
            shift
            ;;
        --full-only)
            BUILD_SLIM=false
            shift
            ;;
        --version|-v)
            VERSION="$2"
            shift 2
            ;;
        --name|-n)
            IMAGE_NAME="$2"
            shift 2
            ;;
        --registry|-r)
            REGISTRY="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --slim-only    Build only slim version (no browser)"
            echo "  --full-only    Build only full version (with browser)"
            echo "  --version, -v  Set version tag (default: latest)"
            echo "  --name, -n     Set image name (default: babyclaw)"
            echo "  --registry, -r Set registry (default: agentscope)"
            echo "  --help, -h     Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Build both slim and full versions"
            echo "  $0 --slim-only        # Build only slim version"
            echo "  $0 --version 1.0.0    # Build version 1.0.0"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Build versions
if [ "$BUILD_SLIM" = true ]; then
    build_version "slim" "false"
fi

if [ "$BUILD_FULL" = true ]; then
    build_version "full" "true"
fi

echo "========================================"
echo "Build complete!"
echo "========================================"
echo ""
echo "Built images:"
docker images "$REGISTRY/$IMAGE_NAME" --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}" | grep "$VERSION"
echo ""

echo "Quick start commands:"
echo ""
echo "Slim version (recommended):"
echo "  docker run -d -p 8088:8088 ${REGISTRY}/${IMAGE_NAME}:${VERSION}-slim"
echo ""
if [ "$BUILD_FULL" = true ]; then
    echo "Full version (with browser support):"
    echo "  docker run -d -p 8088:8088 ${REGISTRY}/${IMAGE_NAME}:${VERSION}-full"
    echo ""
fi
echo "See docker-compose.yml for configuration options"
