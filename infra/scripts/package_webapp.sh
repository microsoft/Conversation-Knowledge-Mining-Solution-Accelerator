#!/bin/bash

# Package React webapp for Azure App Service deployment
# This script builds the React frontend with dynamic API URL injection
# Run from workspace root OR from src/App (auto-detects location)

set -e

echo "=== React App Build Started ==="

# Detect if we're in src/App or workspace root and navigate accordingly
if [ -f "package.json" ]; then
    # Already in src/App
    echo "Running from src/App directory"
elif [ -f "src/App/package.json" ]; then
    # In workspace root, navigate to src/App
    echo "Navigating to src/App directory"
    cd src/App
else
    echo "ERROR: Cannot find React app. Run from workspace root or src/App directory."
    exit 1
fi

# Clean old build folder to ensure fresh build
if [ -d "build" ]; then
    echo "Cleaning old build folder..."
    rm -rf build
fi

# Get the API URL from azd environment
echo "Fetching API URL from azd environment..."
apiUrl=$(azd env get-value API_APP_URL)

if [ -z "$apiUrl" ]; then
    echo "ERROR: API_APP_URL not found in azd environment. Run 'azd provision' first."
    exit 1
fi

echo "API URL: $apiUrl"

# Set environment variable for React build
export REACT_APP_API_BASE_URL="$apiUrl"
echo "Set REACT_APP_API_BASE_URL=$apiUrl"

# Install dependencies
echo ""
echo "Installing npm dependencies..."
npm install
if [ $? -ne 0 ]; then
    echo "ERROR: npm install failed"
    exit 1
fi

# Build React app
echo ""
echo "Building React application..."
npm run build
if [ $? -ne 0 ]; then
    echo "ERROR: npm run build failed"
    exit 1
fi

echo ""
echo "=== React App Build Complete ==="
echo "Built files are in ./build directory"
