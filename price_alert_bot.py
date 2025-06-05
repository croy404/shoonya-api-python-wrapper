import time
import yaml
import logging
from api_helper import ShoonyaApiPy
from telegram import Bot
from telegram.error import TelegramError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PriceAlertBot:
    def __init__(self, market_cred_path, telegram_token, telegram_chat_id, poll_interval=30):
        self.api = ShoonyaApiPy()
        self.telegram_bot = Bot(token=telegram_token)
        self.chat_id = telegram_chat_id
        self.poll_interval = poll_interval
        self.alerts = {}  # symbol -> {'exchange': str, 'token': str, 'target_price': float, 'direction': 'above'|'below'}
        self.logged_in = False
        self.market_cred_path = market_cred_path

    def login_market_api(self):
        with open(self.market_cred_path, 'r') as f:
            cred = yaml.safe_load(f)
        ret = self.api.login(userid=cred['user'], password=cred['pwd'], twoFA=cred['factor2'],
                             vendor_code=cred['vc'], api_secret=cred['apikey'], imei=cred['imei'])
        if ret is not None:
            self.logged_in = True
            logging.info("Logged in to market API successfully.")
        else:
            logging.error("Failed to login to market API.")
            self.logged_in = False

    def add_alert(self, symbol, exchange, token, target_price, direction):
        """
        Add a price alert.
        direction: 'above' or 'below'
        """
        self.alerts[symbol] = {
            'exchange': exchange,
            'token': token,
            'target_price': target_price,
            'direction': direction
        }
        logging.info(f"Added alert for {symbol}: {direction} {target_price}")

    def fetch_ltp(self, exchange, token):
        try:
            quote = self.api.get_quotes(exchange=exchange, token=token)
            if quote and 'lp' in quote:
                return float(quote['lp'])
            elif quote and 'ltp' in quote:
                return float(quote['ltp'])
            else:
                logging.warning(f"LTP not found in quote for token {token}")
                return None
        except Exception as e:
            logging.error(f"Error fetching LTP for token {token}: {e}")
            return None

    def send_telegram_alert(self, message):
        try:
            self.telegram_bot.send_message(chat_id=self.chat_id, text=message)
            logging.info(f"Sent Telegram alert: {message}")
        except TelegramError as e:
            logging.error(f"Failed to send Telegram message: {e}")

    def check_alerts(self):
        for symbol, alert in self.alerts.items():
            ltp = self.fetch_ltp(alert['exchange'], alert['token'])
            if ltp is None:
                continue
            target = alert['target_price']
            direction = alert['direction']
            if direction == 'above' and ltp > target:
                self.send_telegram_alert(f"Price Alert: {symbol} LTP {ltp} crossed above {target}")
                # Remove alert after triggered
                del self.alerts[symbol]
                break
            elif direction == 'below' and ltp < target:
                self.send_telegram_alert(f"Price Alert: {symbol} LTP {ltp} crossed below {target}")
                # Remove alert after triggered
                del self.alerts[symbol]
                break

    def run(self):
        self.login_market_api()
        if not self.logged_in:
            logging.error("Cannot start alert bot without market API login.")
            return

        logging.info("Starting price alert bot...")
        try:
            while True:
                if not self.alerts:
                    logging.info("No alerts set. Waiting...")
                else:
                    self.check_alerts()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            logging.info("Price alert bot stopped by user.")

if __name__ == "__main__":
    import os

    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    MARKET_CRED_PATH = 'cred.yml'  # Path to market API credentials

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.")
        exit(1)

    bot = PriceAlertBot(MARKET_CRED_PATH, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)

    # Example usage: add alerts here or extend to accept user input
    # Format: add_alert(symbol, exchange, token, target_price, direction)
    bot.add_alert('RELIANCE-EQ', 'NSE', '22', 2500.0, 'above')
    bot.add_alert('TCS-EQ', 'NSE', '33', 3000.0, 'below')

    bot.run()
