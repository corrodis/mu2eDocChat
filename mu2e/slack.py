import mu2e
from mu2e.chat_mcp import Chat
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.errors import SlackApiError
import time
import asyncio
from datetime import datetime
import pytz
import os
import re

class slack:
    """
    Attributes:
        client (slack_sdk.WebClient)
        socket (slack_sdk.socket_mode.SocketModeClient)
        channel_id (str): channel id used to send and fetch messages
        latest_ts (timestamp): last time checked for new messages
    """
    def __init__(self, channel_name=None):
        """
        Args:
            channel_name(str): name of the channel to be used, or None for DMs only
        """
        self.bot_token = os.getenv('MU2E_SLACK_BOT_TOKEN')
        self.app_token = os.getenv('MU2E_SLACK_APP_TOKEN')
        
        if not self.bot_token:
            raise ValueError("Slack bot token not found. Please set MU2E_SLACK_BOT_TOKEN environment variable")
        if not self.app_token:
            raise ValueError("Slack app token not found. Please set MU2E_SLACK_APP_TOKEN environment variable")

        self.client = WebClient(self.bot_token)
        self.socket = SocketModeClient(app_token=self.app_token)
        
        if channel_name:
            self.channel_id = self._find_channel_id(channel_name)
            if not self.channel_id:
                raise ValueError(f"Could not find channel: {channel_name}")
        else:
            self.channel_id = None  # Support DMs
            
        self.latest_ts = time.time()
        self.threads = {} # store active threads
        self.processor = Chat
        self.bot_user_id = None  # Will be set when we connect
        self._shutdown_requested = False
        self.show_tool_notifications = True  # Can be disabled

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

    def _get_bot_user_id(self):
        """Get the bot's user ID"""
        try:
            response = self.client.auth_test()
            return response["user_id"]
        except SlackApiError as e:
            print(f"Error getting bot user ID: {e}")
            return None

    def _is_mention(self, text, user_id):
        """Check if the bot is mentioned in the text"""
        return f'<@{user_id}>' in text

    def _is_direct_message(self, channel):
        """Check if this is a direct message (channel starts with 'D')"""
        return channel.startswith('D')

    def _clean_mention(self, text, user_id):
        """Remove bot mention from text"""
        mention_pattern = f'<@{user_id}>'
        return re.sub(mention_pattern, '', text).strip()

    def _schedule_async_task(self, coro):
        """Schedule an async task in the main event loop"""
        if hasattr(self, '_main_loop') and self._main_loop:
            # Use the main event loop we stored
            asyncio.run_coroutine_threadsafe(coro, self._main_loop)
        else:
            # Fallback - this should not happen if properly initialized
            print("Warning: No main event loop available, task may not persist")
            import threading
            def run_async():
                asyncio.run(coro)
            thread = threading.Thread(target=run_async)
            thread.daemon = True
            thread.start()

    def _format_for_slack(self, text):
        """Format response text for better Slack display"""
        import re
        
        # Convert markdown links to Slack format: [text](url) -> <url|text>
        text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<\2|\1>', text)
        
        # Convert mu2e document references to nicer format
        text = re.sub(r'<https://mu2e-docdb\.fnal\.gov/cgi-bin/sso/ShowDocument\?docid=(\d+)\|mu2e-docdb-(\d+)>', 
                     r'📄 <https://mu2e-docdb.fnal.gov/cgi-bin/sso/ShowDocument?docid=\1|Mu2e Doc \1>', text)
        
        # Convert markdown headers to bold text
        text = re.sub(r'^## (.+)$', r'*\1*', text, flags=re.MULTILINE)
        text = re.sub(r'^### (.+)$', r'*\1*', text, flags=re.MULTILINE)
        text = re.sub(r'^#### (.+)$', r'*\1*', text, flags=re.MULTILINE)
        
        # Convert **bold** to *bold* (Slack format)
        text = re.sub(r'\*\*([^*]+)\*\*', r'*\1*', text)
        
        # Improve list formatting with simple bullets
        text = re.sub(r'^- (.+)$', r'• \1', text, flags=re.MULTILINE)
        
        # Add spacing around headers for better readability
        text = re.sub(r'\n(\*[^*]+\*)\n', r'\n\n\1\n', text)
        
        # Clean up excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text

    def send(self, message, thread_ts=None, channel=None):
        target_channel = channel or self.channel_id
        formatted_message = self._format_for_slack(message)
        result = self.client.chat_postMessage(
            channel=target_channel,
            thread_ts=thread_ts,
            text=formatted_message
        )
        return result.status_code == 200

    def monitor(self):
        # Store the main event loop for async task scheduling
        try:
            self._main_loop = asyncio.get_running_loop()
        except RuntimeError:
            self._main_loop = None
            print("Warning: No event loop running when starting monitor")
            
        # Get bot user ID for mention detection
        if not self.bot_user_id:
            self.bot_user_id = self._get_bot_user_id()
            
        def process_event(client: SocketModeClient, req: SocketModeRequest):
            if req.type == "events_api":
                response = SocketModeResponse(envelope_id=req.envelope_id)
                client.send_socket_mode_response(response)

                event = req.payload["event"]
                
                # Skip bot messages and certain subtypes
                if "bot_id" in event or event["type"] != "message":
                    return
                    
                if 'subtype' in event and event['subtype'] == "channel_join":
                    return

                channel = event.get("channel")
                text = event.get("text", "")
                
                # Determine if we should respond
                should_respond = False
                
                if self._is_direct_message(channel):
                    # Always respond to DMs
                    should_respond = True
                elif "thread_ts" in event and event["thread_ts"] in self.threads:
                    # Always respond in threads we're participating in
                    should_respond = True
                    # Clean mention if present but don't require it
                    if self.bot_user_id and self._is_mention(text, self.bot_user_id):
                        text = self._clean_mention(text, self.bot_user_id)
                        event["text"] = text
                elif self.channel_id and channel == self.channel_id:
                    # In configured channel, respond to mentions
                    if self.bot_user_id and self._is_mention(text, self.bot_user_id):
                        should_respond = True
                        # Clean the mention from text
                        text = self._clean_mention(text, self.bot_user_id)
                        event["text"] = text
                elif self.channel_id is None:
                    # No specific channel configured, respond to mentions in any channel
                    if self.bot_user_id and self._is_mention(text, self.bot_user_id):
                        should_respond = True
                        text = self._clean_mention(text, self.bot_user_id)
                        event["text"] = text

                if should_respond:
                    if "thread_ts" not in event:  # new thread
                        ts_ = event["ts"]
                        self.threads[ts_] = {
                            'ts': datetime.now().timestamp(),
                            'channel': channel
                        }
                        # Schedule the async task
                        self._schedule_async_task(self.process_async(event, ts_))
                        self.latest_ts = ts_
                    else: 
                        thread_ts = event.get("thread_ts")
                        if thread_ts in self.threads:
                            self._schedule_async_task(self.process_async(event, thread_ts))
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

    async def _status_notification(self, message: str, metadata: dict, channel: str, thread_ts: str):
        """Send a status notification"""
        if not self.show_tool_notifications:
            return
            
        status_type = metadata.get("type", "unknown")
        
        # Filter out context updates (token counts) from Slack notifications
        if status_type == "context_update":
            return
        
        # Add appropriate emoji based on status type
        if status_type == "tool_start":
            emoji = "🔍"
        elif status_type == "tool_result":
            emoji = "📊"
        elif status_type == "agent_start":
            emoji = "🤖"
        elif status_type == "agent_complete":
            emoji = "✅"
        else:
            emoji = "ℹ️"
        
        description = f"{emoji} {message}"
        
        # Add additional context if available
        if status_type == "tool_start" and "arguments" in metadata:
            arguments = metadata["arguments"]
            if "query" in arguments:
                query = arguments["query"]
                if len(query) > 50:
                    query = query[:47] + "..."
                description += f" for '{query}'"
            elif "docid" in arguments:
                description += f" (ID: {arguments['docid']})"
        
        # Send notification in thread
        thread_ts_for_notification = thread_ts if not self._is_direct_message(channel) else None
        self.send(description, thread_ts=thread_ts_for_notification, channel=channel)

    async def process_async(self, message, ts):
        """Process a message asynchronously using the MCP chat"""
        try:
            # Create chat instance for this thread if it doesn't exist
            if "chat" not in self.threads[ts]:
                # Get user info for context
                user = message["user"]
                channel = self.threads[ts]["channel"]
                
                try:
                    user_info = self.client.users_info(user=user)["user"]
                    user_name = user_info.get("real_name") or user_info.get("name", "Unknown")
                except Exception:
                    user_name = "Unknown"
                
                # Build user context
                user_context = {
                    "user_name": user_name,
                    "interface":"slack"
                }
                
                # Add Slack channel URL and message URL if not a DM
                if not self._is_direct_message(channel):
                    try:
                        channel_info = self.client.conversations_info(channel=channel)["channel"]
                        channel_name = channel_info.get("name", "unknown")
                        user_context["slack_channel_name"] = channel_name
                        # Slack channel URL format
                        workspace_domain = self.client.auth_test()
                        user_context["slack_workspace_name"] = workspace_domain["name"]
                        user_context["slack_message_ts"] = ts
                        # Add message URL
                        ts_for_url = ts.replace(".", "")
                        user_context["slack_message_url"] = f"{workspace_domain['url']}archives/{channel}/p{ts_for_url}"
                    except Exception:
                        pass  # Skip if we can't get channel info
                
                chat_instance = self.processor(user_context=user_context)
                
                # Set up status callback for this chat instance
                async def status_callback(message, metadata):
                    await self._status_notification(message, metadata, channel, ts)
                
                chat_instance.set_status_callback(status_callback)
                self.threads[ts]["chat"] = chat_instance
            
            user = message["user"]
            text = message["text"]
            channel = self.threads[ts]["channel"]
            
            print(f"Processing message in thread {ts}: {text}")
            
            # Get response from chat (context was set at creation time)
            answer = await self.threads[ts]["chat"].chat(text)
            
            if answer:
                # Send response in thread (or directly for DMs)
                thread_ts = ts if not self._is_direct_message(channel) else None
                self.send(answer, thread_ts=thread_ts, channel=channel)
                print(f"Sent response: {answer[:100]}...")
            
        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            print(f"Error processing message: {e}")
            channel = self.threads[ts]["channel"]
            thread_ts = ts if not self._is_direct_message(channel) else None
            self.send(error_msg, thread_ts=thread_ts, channel=channel)
            

    async def cleanup_threads(self):
        """Clean up old inactive threads"""
        current_time = datetime.now().timestamp()
        inactive_threads = []
        
        for ts, thread_data in self.threads.items():
            # Remove threads inactive for more than 1 hour
            if current_time - thread_data['ts'] > 3600:
                inactive_threads.append(ts)
        
        for ts in inactive_threads:
            if "chat" in self.threads[ts]:
                await self.threads[ts]["chat"].cleanup()
            del self.threads[ts]
            print(f"Cleaned up inactive thread: {ts}")

    async def shutdown(self):
        """Gracefully shutdown the bot and clean up all resources"""
        print("Shutting down Slack bot...")
        self._shutdown_requested = True
        
        # Clean up all active chat instances
        for ts, thread_data in self.threads.items():
            if "chat" in thread_data:
                try:
                    await thread_data["chat"].cleanup()
                    print(f"Cleaned up chat for thread {ts}")
                except Exception as e:
                    print(f"Error cleaning up thread {ts}: {e}")
        
        # Disconnect from Slack
        try:
            self.socket.disconnect()
            print("Disconnected from Slack")
        except Exception as e:
            print(f"Error disconnecting from Slack: {e}")
        
        print("Slack bot shutdown complete")
