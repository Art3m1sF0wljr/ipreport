import ftplib
import requests
import time
import os
from datetime import datetime
from dotenv import load_dotenv
import io

# Load environment variables from a .env file (optional)
load_dotenv()

# FTPS server credentials
FTP_HOST = os.getenv('FTP_HOST')
FTP_USER = os.getenv('FTP_USER')
FTP_PASS = os.getenv('FTP_PASS')
REMOTE_PATH = '/my/path/for/'

# Function to get the current public IP with fallback
def get_current_ip():
    services = [
        'https://api.ipify.org',
        'https://ifconfig.me/ip',
        'https://icanhazip.com'
    ]
    for service in services:
        try:
            response = requests.get(service, timeout=5)
            if response.status_code == 200:
                return response.text.strip()
        except requests.RequestException:
            continue
    print("Failed to fetch public IP from all services.")
    return None

# Function to connect securely to the FTPS server
def connect_ftps():
    try:
        ftps = ftplib.FTP_TLS(FTP_HOST)
        ftps.login(FTP_USER, FTP_PASS)
        ftps.prot_p()  # Secure data connection (Explicit TLS)
        ftps.set_pasv(True)  # Enable passive mode
        return ftps
    except ftplib.all_errors as e:
        print(f"FTPS connection error: {e}")
        return None

# Function to update ip.txt and log.txt securely
def update_ftps(ip, last_ip):
    ftps = connect_ftps()
    if not ftps:
        return

    try:
        ftps.cwd(REMOTE_PATH)

        # Overwrite ip.txt with the current IP
        ftps.storlines('STOR ip.txt', io.StringIO(ip))

        # Append to log.txt if the IP has changed
        if ip != last_ip:
            log_entry = f"{datetime.now().isoformat()} - {ip}\n"

            # Retrieve existing log.txt if present
            try:
                existing_log = []
                ftps.retrlines('RETR log.txt', existing_log.append)
                existing_log = '\n'.join(existing_log) + '\n'
            except ftplib.error_perm:
                existing_log = ''  # log.txt doesn't exist yet

            # Append new log entry
            ftps.storlines('STOR log.txt', io.StringIO(existing_log + log_entry))

    except ftplib.all_errors as e:
        print(f"Error updating files on FTPS: {e}")
    finally:
        ftps.quit()

# Main loop with secure practices
last_ip = ''
while True:
    current_ip = get_current_ip()
    if current_ip:
        update_ftps(current_ip, last_ip)
        last_ip = current_ip
    time.sleep(30)
