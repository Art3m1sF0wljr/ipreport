import requests
import time
import logging
import subprocess

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

CHECK_INTERVAL = 30  # seconds
CONNECTION_TIMEOUT = 15  # seconds for all network operations
REBOOT_AFTER_FAILURES = 3  # Number of consecutive failures before rebooting

def test_internet_connection():
    """
    Test internet connectivity by attempting to connect to multiple IP services.
    
    Returns:
        bool: True if at least one service responds successfully, False otherwise.
    """
    services = [
        'https://api.ipify.org',
        'https://ifconfig.me/ip',
        'https://icanhazip.com',
        'https://httpbin.org/ip',
        'https://checkip.amazonaws.com'
    ]
    
    successful_connections = 0
    
    for service in services:
        try:
            response = requests.get(service, timeout=CONNECTION_TIMEOUT)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            
            # If we get here, the request was successful
            logging.info(f"Successfully connected to {service}")
            successful_connections += 1
            # We don't need to check all services if one works
            break
            
        except requests.exceptions.Timeout:
            logging.warning(f"Timeout when connecting to {service}")
        except requests.exceptions.ConnectionError:
            logging.warning(f"Connection error when connecting to {service}")
        except requests.exceptions.HTTPError as e:
            logging.warning(f"HTTP error when connecting to {service}: {e}")
        except requests.RequestException as e:
            logging.warning(f"Request exception when connecting to {service}: {e}")
    
    # Return True if at least one service responded successfully
    return successful_connections > 0

def reboot_system():
    """
    Reboot the system using sudo reboot command.
    """
    logging.error("Internet connection lost. Rebooting system...")
    try:
        subprocess.run(['sudo', 'reboot'], check=True, timeout=30)
        logging.info("Reboot command executed successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to reboot system (process error): {e}")
    except subprocess.TimeoutExpired:
        logging.error("Reboot command timed out.")
    except Exception as e:
        logging.error(f"Unexpected error during reboot: {e}")

def main():
    """
    Main monitoring loop to check internet connectivity and reboot if connection fails.
    """
    consecutive_failures = 0
    
    logging.info("Internet connectivity monitor started.")
    logging.info(f"Will reboot after {REBOOT_AFTER_FAILURES} consecutive failures")
    
    while True:
        try:
            # Test internet connection
            if test_internet_connection():
                # Connection successful
                if consecutive_failures > 0:
                    logging.info(f"Internet connection restored after {consecutive_failures} failures")
                    consecutive_failures = 0
                else:
                    logging.debug("Internet connection is active")
            else:
                # Connection failed
                consecutive_failures += 1
                logging.warning(f"Internet connection failed. Consecutive failures: {consecutive_failures}")
                
                # Check if we've reached the failure threshold
                if consecutive_failures >= REBOOT_AFTER_FAILURES:
                    logging.error(f"Maximum consecutive failures ({REBOOT_AFTER_FAILURES}) reached. No internet connectivity.")
                    reboot_system()
                    # If reboot command doesn't work, wait before continuing loop
                    time.sleep(60)
                    continue
            
            # Wait before next check
            logging.debug(f"Waiting {CHECK_INTERVAL} seconds before next check...")
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            logging.info("Monitoring interrupted by user.")
            break
        except Exception as e:
            consecutive_failures += 1
            logging.error(f"Unexpected error in main loop: {e}")
            logging.warning(f"Consecutive failures: {consecutive_failures}")
            
            # Check if we should reboot due to critical errors
            if consecutive_failures >= REBOOT_AFTER_FAILURES:
                logging.error("Critical errors reached reboot threshold. Rebooting...")
                reboot_system()
                time.sleep(60)
            else:
                logging.warning("Waiting before retrying after critical error...")
                time.sleep(30)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"Fatal error in application: {e}")
        # Attempt to reboot even on fatal startup errors
        logging.error("Attempting reboot due to fatal startup error...")
        reboot_system()
        raise
