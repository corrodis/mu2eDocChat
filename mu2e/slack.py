import mu2e
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.errors import SlackApiError
import time
from datetime import datetime
import pytz

class slack:
    """
    Attributes:
        client (slack_sdk.WebClient)
        socket (slack_sdk.socket_mode.SocketModeClient)
        channel_id (str): channel id used to send and fetch messages
        latest_ts (timestamp): last time checked for new messages
    """
    def __init__(self, channel_name):
        """
        Args:
            channel_name(str): name of the channel to be used
        """
        self.client = WebClient(mu2e.api_keys['slack'])
        self.socket = SocketModeClient(app_token=mu2e.api_keys['slack-app'])
        self.channel_id = self._find_channel_id(channel_name)
        self.latest_ts = time.time()
        self.threads = {} # store active threads
        self.processor = p

    def __del__(self):
        #print("DEBUG DEL")
        self.socket.disconnect()

    def _find_channel_id(self, channel_name):
        conversation_id = None
        try:
            # Call the conversations.list method using the WebClient
            for result in self.client.conversations_list():
                if conversation_id is not None:
                    break
                for channel in result["channels"]:
                    #print(channel["name"])
                    if channel["name"] == channel_name:
                        return channel["id"]
        
        except SlackApiError as e:
            print(f"Error: {e}")
        return None

    def send(self, message,thread_ts=None):
        result = self.client.chat_postMessage(
            channel=self.channel_id,
            thread_ts=thread_ts,
            text=message
        )
        return result.status_code == 200

    def monitor(self):
        #print("monitor")
        def process_event(client: SocketModeClient, req: SocketModeRequest):
            #print("process_event")
            if req.type == "events_api":
                response = SocketModeResponse(envelope_id=req.envelope_id) # Acknowledge the request
                client.send_socket_mode_response(response)

                event = req.payload["event"]
                #print(event['text'], "bot_id" in event)
                if "bot_id" not in event and event["type"] == "message":
                    if 'subtype' in event:
                        if event['subtype'] == "channel_join":
                            return
                            
                    # filter channels
                    #print(self.channel_id, event.get("channel"), self.channel_id == event.get("channel"))
                    if self.channel_id == event.get("channel") or (self.channel_id is None):
                        # new thread or part of a thread?
                        #print("DEBUG: ", event)
                        if "thread_ts" not in event: # new thread
                            print("NEW")
                            ts_ = event["ts"]
                            self.threads[ts_] = {'ts':datetime.now().timestamp()}
                            self.process(event, ts_)
                            self.latest_ts = ts_
                        else: 
                            thread_ts = event.get("thread_ts")
                            self.process(event, thread_ts)
                            self.threads[thread_ts]['ts'] = datetime.now().timestamp()
        
        self.socket.socket_mode_request_listeners.append(process_event)
        print("connect to the websocket")
        self.socket.connect()
        #import signal
        #signal.pause()
                        
    
    def fetch(self):
        try:
            result = self.client.conversations_history(
                channel=self.channel_id,
                oldest=self.latest_ts
            )
    
            # Process new messages
            messages = result["messages"]
            print(messages)
            for message in messages:
                if "bot_id" not in message and message['type'] == "message":  # Ignore bot messages
                    if 'subtype' in message:
                        if message['subtype'] == "channel_join":
                            continue

                    ts_ = message["ts"]
                    self.threads[ts_] = {'ts':datetime.now().timestamp()}
                    self.process(message, ts_)
                    self.latest_ts = ts_
            
            # check all active threads for new messages
            for ts in self.threads.keys():
                result = self.client.conversations_replies(
                    channel=self.channel_id,
                    ts=ts
                )
                messages = result["messages"]
                if "bot_id" not in messages[-1]:
                    self.ts_latest = messages[-1]["ts"] # ts of latest message
                    text = messages[-1]["text"]
                    if float(self.ts_latest) > self.threads[ts]['ts']:
                        self.process(messages[-1], ts)
                        self.threads[ts]['ts'] = datetime.now().timestamp()

        except SlackApiError as e:
            print(f"Error fetching messages: {e}")

    def process(self, message, ts):
        print("DEBUG000", message)
        print(ts in self.threads)
        if "chat" not in self.threads[ts]:
            print("DEBUG01")
            self.threads[ts]["chat"] = self.processor()
        print("DEBUG1")
        user = message["user"]
        text = message["text"]
        #ts = message["ts"]
        typ = message["type"]
        print("DEBUG12")
        #user_info = self.client.users_info(user=user)["user"]
        #tz = pytz.timezone(user_info["tz"])
        #query = '<user name="'+user_info["name"]+'" local_time="'+datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z%z")+'">' + text
        #query = "Just for background, my name is "+user_info["name"]+", local time is "+datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z%z")
        query = text
        print("DEBUG2", query)
        answer = self.threads[ts]["chat"](query)
        print("process answer", answer)
        if answer:
            self.send(answer,thread_ts=ts)
            

class p:
    def __init__(self):
        self.cnt = 0
    def __call__(self, msg):
        self.cnt = self.cnt + 1
        print(f"{self.cnt}) {msg}")
        return "done"