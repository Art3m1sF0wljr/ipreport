import ftplib
import requests
import time
import os
from datetime import datetime
from dotenv import load_dotenv
import io
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables from a .env file
load_dotenv()

# FTPS server credentials
FTP_HOST = os.getenv('FTP_HOST')
FTP_USER = os.getenv('FTP_USER')
FTP_PASS = os.getenv('FTP_PASS')
REMOTE_PATH = '/ip/'

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
        except requests.RequestException as e:
            logging.warning(f"Failed to fetch IP from {service}: {e}")
    logging.error("Failed to fetch public IP from all services.")
    return None

# Function to connect securely to the FTPS server
def connect_ftps():
    try:
        ftps = ftplib.FTP_TLS(FTP_HOST)
        ftps.login(FTP_USER, FTP_PASS)
        ftps.prot_p()  # Secure data connection (Explicit TLS)
        ftps.set_pasv(True)  # Enable passive mode
        logging.info("Successfully connected to the FTPS server.")
        return ftps
    except ftplib.all_errors as e:
        logging.error(f"FTPS connection error: {e}")
        return None

# Function to update ip.txt and log.txt securely
def update_ftps(ip, last_ip):
    ftps = connect_ftps()
    if not ftps:
        return

    try:
        ftps.cwd(REMOTE_PATH)

        # Overwrite ip.txt with the current IP (fix: using BytesIO)
        ftps.storbinary('STOR ip.txt', io.BytesIO(ip.encode('utf-8')))
        logging.info(f"Updated ip.txt with IP: {ip}")

        # Append to log.txt if the IP has changed
        if ip != last_ip:
            log_entry = f"{datetime.now().isoformat()} - {ip}\n"

            # Retrieve existing log.txt if present
            existing_log = ''
            try:
                with io.BytesIO() as bio:
                    ftps.retrbinary('RETR log.txt', bio.write)
                    existing_log = bio.getvalue().decode('utf-8')
            except ftplib.error_perm:
                logging.info("log.txt does not exist. Creating a new one.")

            # Append new log entry
            updated_log = existing_log + log_entry
            ftps.storbinary('STOR log.txt', io.BytesIO(updated_log.encode('utf-8')))
            logging.info(f"Appended new IP to log.txt: {ip}")
        else:
            logging.info("IP has not changed. No update to log.txt.")

    except ftplib.all_errors as e:
        logging.error(f"Error updating files on FTPS: {e}")
    finally:
        try:
            ftps.quit()  # Graceful disconnect
            logging.info("FTPS connection closed.")
        except ftplib.all_errors as e:
            logging.warning(f"Error closing FTPS connection: {e}")

# Main loop with secure practices
last_ip = ''
while True:
    current_ip = get_current_ip()
    if current_ip:
        update_ftps(current_ip, last_ip)
        last_ip = current_ip
    time.sleep(30)

