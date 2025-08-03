#!/bin/bash
echo "📦 Setting up RazorBot..."
cd "$(dirname "$0")"
mkdir -p ~/razorbot_backups

# Set up Python venv
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Prompt for token
read -p "Enter your Discord Bot Token: " TOKEN
export TOKEN="$TOKEN"

# Insert token into bot.py
sed -i "s|TOKEN = \"\"|TOKEN = \\\"$TOKEN\\\"|" bot.py

# Run bot
python bot.py
