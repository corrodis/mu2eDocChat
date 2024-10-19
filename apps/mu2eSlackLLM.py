import mu2e
from mu2e import chat
from mu2e import slack
import time

class bot:
    def __init__(self):
        self.chat = chat.chat()
    def __call__(self, msg):
        # handle slack commands that effect the settings, models and so on
        print("bot called", msg)
        
        return self.chat(msg)

if __name__ == "__main__":
    s = slack.slack("llm_tests")
    s.processor = bot
    s.monitor()
    #import signal
    #signal.pause()
    while True:
        print("still running")
         #print("fetch")
    #    #s.fetch()
        time.sleep(1)
        