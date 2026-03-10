import asyncio
import logging
import sys
import argparse
from src.gbot.config import load_config
from src.gbot.mcp_client import GmonClient
from src.gbot.mcp_mock import MockGmonClient
from src.gbot.brain import GeminiBrain
from src.gbot.scheduler import GbotScheduler
from src.gbot.calendar_sync import CalendarSync
from src.gbot.channels.google_chat import GoogleChatInterface
from src.gbot.channels.gmail_poller import GmailPoller

logging.basicConfig(level=logging.INFO, format='%(asctime)s - gbot - %(levelname)s - %(message)s')
logger = logging.getLogger("main")

class GbotApp:
    def __init__(self, is_test=False):
        self.config = load_config()
        self.is_test = is_test
        
        # Initialize Gmon Client (Mocked if in test mode)
        if self.is_test:
            self.gmon = MockGmonClient()
        else:
            self.gmon = GmonClient()
            
        # Initialize Brain
        self.brain = GeminiBrain()
        
        # Initialize Channels
        self.chat = GoogleChatInterface(self.config, self.brain.query)
        self.gmail = GmailPoller(self.config, self.brain.query)
        
        # Initialize Scheduler & Sync
        self.scheduler = GbotScheduler(self.gmon, self.chat)
        self.calendar = CalendarSync(self.config, self.scheduler)

    async def run(self):
        logger.info(f"Starting gbot (Test Mode: {self.is_test})")
        
        # 1. Connect to gmon
        try:
            await self.gmon.connect()
            logger.info("Connected to gmon.")
        except Exception as e:
            if not self.is_test:
                logger.error(f"Failed to connect to gmon: {e}")
                return
            logger.warning(f"Gmon connection failed, but continuing in test mode: {e}")

        # 2. Start background tasks
        tasks = [
            asyncio.create_task(self.scheduler.run_loop()),
            asyncio.create_task(self.calendar.run_loop()),
            asyncio.create_task(self.gmail.poll_forever())
        ]
        
        logger.info("gbot is now fully operational.")
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Shutdown requested.")
        finally:
            await self.gmon.disconnect()

async def main():
    parser = argparse.ArgumentParser(description="gbot Intelligent Gateway")
    parser.add_argument("-test", action="store_true", help="Run in test mode with mocked MCP")
    args = parser.parse_args()

    app = GbotApp(is_test=args.test)
    try:
        await app.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
