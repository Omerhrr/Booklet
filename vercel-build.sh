#!/bin/bash

# This script runs during the Vercel build process.
# It updates the package list and installs the system-level dependencies
# required by the WeasyPrint library for PDF generation.

echo "--- Installing WeasyPrint System Dependencies ---"
apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0

echo "--- System Dependencies Installation Complete ---"
