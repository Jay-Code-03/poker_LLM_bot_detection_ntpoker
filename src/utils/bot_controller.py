import signal
import sys
from threading import Event

class BotController:
    def __init__(self):
        self.stop_event = Event()
        self._setup_signal_handler()
    
    def _setup_signal_handler(self):
        # Handle Ctrl+C (SIGINT) gracefully
        signal.signal(signal.SIGINT, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        print("\nReceived signal to stop. Shutting down gracefully...")
        self.stop_bot()
    
    def stop_bot(self):
        print("\nStopping bot...")
        self.stop_event.set()
    
    def should_continue(self):
        return not self.stop_event.is_set()
    
    def cleanup(self):
        sys.exit(0)