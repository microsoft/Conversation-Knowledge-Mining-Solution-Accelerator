#!/bin/bash

# Package web app for Azure App Service deployment
# This script packages the application for local deployment

set -e

echo "Starting web app packaging for App Service..."

# Get the script directory and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SRC_DIR="$PROJECT_ROOT/src"
DIST_DIR="$SRC_DIR/dist"

echo "Project root: $PROJECT_ROOT"
echo "Source directory: $SRC_DIR"
echo "Dist directory: $DIST_DIR"

# Clean dist directory if it exists
if [ -d "$DIST_DIR" ]; then
    echo "Cleaning existing dist directory..."
    rm -rf "$DIST_DIR"
fi

# Create dist directory
echo "Creating dist directory..."
mkdir -p "$DIST_DIR"

# Step 1: Copy backend files
echo ""
echo "Step 1: Copying backend API files..."

# Copy Python files and backend code
FILES_TO_COPY=(
    "gunicorn.conf.py"
    "start.sh"
    "start.cmd"
    "asset-manifest.json"
    "manifest.json"
    "favicon-16x16.png"
    "favicon-32x32.png"
)

for file in "${FILES_TO_COPY[@]}"; do
    if [ -f "$SRC_DIR/$file" ]; then
        echo "  Copying $file"
        cp "$SRC_DIR/$file" "$DIST_DIR/"
    fi
done

# Copy api directory (backend)
if [ -d "$SRC_DIR/api" ]; then
    echo "  Copying api directory..."
    cp -r "$SRC_DIR/api" "$DIST_DIR/"
fi

# Step 2: Build frontend
echo ""
echo "Step 2: Building frontend..."
APP_DIR="$SRC_DIR/App"

if [ ! -d "$APP_DIR/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd "$APP_DIR"
    npm ci
    cd "$PROJECT_ROOT"
fi

echo "Running frontend build..."
cd "$APP_DIR"
export NODE_OPTIONS=--max_old_space_size=8192
npm run build
unset NODE_OPTIONS
cd "$PROJECT_ROOT"

# Step 3: Copy App directory (frontend source)
echo ""
echo "Step 3: Copying App directory (frontend)..."
if [ -d "$APP_DIR" ]; then
    echo "  Copying App directory..."
    cp -r "$APP_DIR" "$DIST_DIR/"
fi

# Verify the dist directory
FILE_COUNT=$(find "$DIST_DIR" -type f | wc -l)
DIST_SIZE=$(du -sh "$DIST_DIR" | cut -f1)

echo ""
echo "✓ Successfully prepared deployment package!"
echo "  Dist location: $DIST_DIR"
echo "  Total files: $FILE_COUNT"
echo "  Total size: $DIST_SIZE"

echo ""
echo "Packaging complete! azd will handle zip creation during deployment."
