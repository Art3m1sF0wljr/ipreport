import ftplib
import requests
import time
import os
from datetime import datetime
from dotenv import load_dotenv
import io
import logging
import socket
import subprocess

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables from a .env file
load_dotenv()

# Configuration
FTP_HOST = os.getenv('FTP_HOST')
FTP_USER = os.getenv('FTP_USER')
FTP_PASS = os.getenv('FTP_PASS')
REMOTE_PATH = '/ip/'
CHECK_INTERVAL = 30  # seconds
MAX_RETRIES = 3
CONNECTION_TIMEOUT = 15  # seconds for all network operations
REBOOT_AFTER_FAILURES = 5  # Number of consecutive failures before rebooting

# Function to get the current public IP with fallback
def get_current_ip():
    services = [
        'https://api.ipify.org',
        'https://ifconfig.me/ip',
        'https://icanhazip.com'
    ]
    for service in services:
        try:
            response = requests.get(service, timeout=CONNECTION_TIMEOUT)
            if response.status_code == 200:
                return response.text.strip()
        except requests.RequestException as e:
            logging.warning(f"Failed to fetch IP from {service}: {e}")
    logging.error("Failed to fetch public IP from all services.")
    return None

# Function to connect securely to the FTPS server with timeout
def connect_ftps():
    try:
        # Set socket timeout before creating connection
        socket.setdefaulttimeout(CONNECTION_TIMEOUT)
        
        ftps = ftplib.FTP_TLS(FTP_HOST, timeout=CONNECTION_TIMEOUT)
        ftps.login(FTP_USER, FTP_PASS)
        ftps.prot_p()  # Secure data connection (Explicit TLS)
        ftps.set_pasv(True)  # Enable passive mode
        logging.info("Successfully connected to the FTPS server.")
        return ftps
    except (ftplib.all_errors, socket.timeout, socket.error) as e:
        logging.error(f"FTPS connection error: {e}")
        return None
    finally:
        # Reset default timeout
        socket.setdefaulttimeout(None)

# Function to update files with retries and timeout handling
def update_ftps(ip, last_ip):
    retry_count = 0
    while retry_count < MAX_RETRIES:
        ftps = connect_ftps()
        if not ftps:
            retry_count += 1
            time.sleep(5 * retry_count)  # Exponential backoff
            continue

        try:
            # Set timeout for FTP operations
            ftps.sock.settimeout(CONNECTION_TIMEOUT)
            
            ftps.cwd(REMOTE_PATH)

            # Overwrite ip.txt with the current IP
            with io.BytesIO(ip.encode('utf-8')) as bio:
                ftps.storbinary('STOR ip.txt', bio)

            logging.info(f"Updated ip.txt with IP: {ip}")

            # Update lastupdate.txt with current timestamp
            timestamp = datetime.now().isoformat()
            with io.BytesIO(timestamp.encode('utf-8')) as bio:
                ftps.storbinary('STOR lastupdate.txt', bio)
            logging.info(f"Updated lastupdate.txt with timestamp: {timestamp}")

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
                with io.BytesIO(updated_log.encode('utf-8')) as bio:
                    ftps.storbinary('STOR log.txt', bio)
                logging.info(f"Appended new IP to log.txt: {ip}")
            else:
                logging.info("IP has not changed. No update to log.txt.")

            return True

        except (ftplib.all_errors, socket.timeout, socket.error) as e:
            logging.error(f"Error updating files on FTPS (attempt {retry_count + 1}): {e}")
            retry_count += 1
            time.sleep(5 * retry_count)  # Exponential backoff
        finally:
            try:
                if 'ftps' in locals():
                    ftps.quit()
                    logging.info("FTPS connection closed.")
            except Exception as e:
                logging.warning(f"Error closing FTPS connection: {e}")

    logging.error(f"Failed to update FTPS after {MAX_RETRIES} attempts.")
    return False

# Function to reboot the system
def reboot_system():
    logging.error("No successful updates for too long. Rebooting system...")
    try:
        subprocess.run(['sudo', 'reboot'], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to reboot system: {e}")

# Main loop with watchdog timer
last_successful_update = time.time()
last_ip = ''
consecutive_failures = 0

while True:
    try:
        current_time = time.time()
        
        # Check if we're stuck
        if current_time - last_successful_update > CHECK_INTERVAL * REBOOT_AFTER_FAILURES:
            logging.warning("No successful updates in a while. Rebooting...")
            time.sleep(5)  # Small delay before restarting
            reboot_system()
            continue

        current_ip = get_current_ip()
        if current_ip:
            success = update_ftps(current_ip, last_ip)
            if success:
                last_ip = current_ip
                last_successful_update = current_time
                consecutive_failures = 0
            else:
                consecutive_failures += 1
        else:
            consecutive_failures += 1
        
        time.sleep(CHECK_INTERVAL)
        
    except Exception as e:
        logging.error(f"Unexpected error in main loop: {e}")
        consecutive_failures += 1
        time.sleep(30)  # Longer delay after critical error
