#!/bin/bash
# VPS Setup Script for VoiceClone on AlmaLinux 9 with CyberPanel/OpenLiteSpeed
# Run this script once on your VPS to set up the project

set -e

PROJECT_PATH="/home/voiceclone.gahfaudio.in/public_html"
DOMAIN="voiceclone.gahfaudio.in"
SERVICE_USER="voiceclone"

echo "=== VoiceClone VPS Setup Script ==="
echo "Project path: $PROJECT_PATH"
echo "Domain: $DOMAIN"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo)"
    exit 1
fi

# Install Python 3.11 if not available
echo "Checking Python version..."
if ! command -v python3.11 &> /dev/null; then
    echo "Installing Python 3.11..."
    dnf install -y python3.11 python3.11-pip python3.11-devel
fi

# Install required system packages
echo "Installing system dependencies..."
dnf install -y gcc gcc-c++ make git ffmpeg

# Create project directory if it doesn't exist
mkdir -p "$PROJECT_PATH"
mkdir -p "$PROJECT_PATH/data/voices"
mkdir -p "$PROJECT_PATH/logs"

# Clone the repository if not already cloned
if [ ! -d "$PROJECT_PATH/.git" ]; then
    echo "Cloning repository..."
    cd "$PROJECT_PATH"
    git init
    git remote add origin https://github.com/rahul4webdev/voiceclone.git
    git fetch origin main
    git checkout main
else
    echo "Repository already exists, pulling latest..."
    cd "$PROJECT_PATH"
    git fetch origin main
    git reset --hard origin/main
fi

# Create virtual environment
echo "Setting up Python virtual environment..."
cd "$PROJECT_PATH"
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -e ".[dev]"

# Copy .env.example to .env if not exists
if [ ! -f "$PROJECT_PATH/.env" ]; then
    cp "$PROJECT_PATH/.env.example" "$PROJECT_PATH/.env"
    echo "Created .env from .env.example"
    echo "IMPORTANT: Please update .env with production values!"
fi

# Create systemd service
echo "Setting up systemd service..."
cp "$PROJECT_PATH/deploy/voiceclone.service" /etc/systemd/system/voiceclone.service

# Adjust service file for correct user
# If voiceclone user doesn't exist, use the website owner
if ! id "$SERVICE_USER" &>/dev/null; then
    # Get the owner of the public_html directory
    SERVICE_USER=$(stat -c '%U' "$PROJECT_PATH")
    sed -i "s/User=voiceclone/User=$SERVICE_USER/" /etc/systemd/system/voiceclone.service
    sed -i "s/Group=voiceclone/Group=$SERVICE_USER/" /etc/systemd/system/voiceclone.service
fi

# Set correct permissions
chown -R $SERVICE_USER:$SERVICE_USER "$PROJECT_PATH"
chmod -R 755 "$PROJECT_PATH"

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable voiceclone
systemctl start voiceclone

# Show status
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Service status:"
systemctl status voiceclone --no-pager

echo ""
echo "=== Next Steps ==="
echo "1. Update $PROJECT_PATH/.env with production values"
echo "2. Configure OpenLiteSpeed proxy to port 8011"
echo "3. Test the API at http://$DOMAIN/health"
echo ""
echo "OpenLiteSpeed Proxy Configuration:"
echo "  - Add a new External App in WebAdmin"
echo "  - Type: Web Server"
echo "  - Name: voiceclone"
echo "  - Address: 127.0.0.1:8011"
echo "  - Max Connections: 100"
echo ""
echo "  - Add Context:"
echo "  - Type: Proxy"
echo "  - URI: /"
echo "  - Web Server: voiceclone"
echo ""
