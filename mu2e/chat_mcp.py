"""
Chat implementation using OpenAI Chat Completions API with MCP Server Integration
"""

import asyncio
import traceback
import json
import os
import logging
import subprocess
import sys
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from openai import OpenAI
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from contextlib import AsyncExitStack
import aiohttp
from dotenv import load_dotenv
from .utils import get_lof_dir

# Load environment variables
load_dotenv()

class MCPClient:
    def __init__(self) -> None:
        self._connected = False
        self.mcp_session = None
        self._url = None

    @classmethod 
    async def create(cls, url): # use async factory
        server = cls()
        server._url = url
        try:
            transport = streamablehttp_client(url=url, timeout=5)
            server._exit_stack = AsyncExitStack()
            read_stream, write_stream, _ = await server._exit_stack.enter_async_context(transport)
            session_context = ClientSession(read_stream, write_stream)
            server.mcp_session = await server._exit_stack.enter_async_context(session_context)
            await server.mcp_session.initialize()
            server._connected = True
            print(f"Connected to MCP server at {url}")
            return server
        except Exception as e:
            print(f"Failed to connect to MCP server at {url}: {e}")
            server._connected = False
            return server

    async def close(self):
        """Close the connection to the MCP server."""
        if hasattr(self, '_exit_stack') and self._exit_stack is not None:
            try:
                await self._exit_stack.aclose()
            except Exception as e:
                print(f"Warning: Error closing MCP connection: {e}")
            finally:
                self._exit_stack = None
                self._connected = False
                self.mcp_session = None

    # support for 'async with'
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def list_tools(self):
        return await self.mcp_session.list_tools()
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        return await self.mcp_session.call_tool(tool_name, arguments)




class Chat:
    """
    Chat using OpenAI Chat Completions API with MCP server integration.
    """
    
    def __init__(
        self,
        base_url: str = None,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        mcp_server_url: str = None,
        mcp_timeout_seconds: int = 10,
        api_key: str = None,
        user_context: dict = None
    ):
        # Load from environment with defaults (chat-specific variables)
        load_dotenv()
        self.base_url = base_url or os.getenv('MU2E_CHAT_BASE_URL', 'http://localhost:55019/v1')
        self.model = model or os.getenv('MU2E_CHAT_MODEL', 'argo:gpt-4o')
        self.mcp_server_url = mcp_server_url or os.getenv('MU2E_CHAT_MCP_URL', 'http://localhost:1223/mcp/')
        self.api_key = api_key or os.getenv('MU2E_CHAT_API_KEY', os.getenv('OPENAI_API_KEY', 'whatever+random'))
        
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key
        )
        self.mcp = None
        self.tools = []
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Conversation history
        self.messages: List[Dict[str, Any]] = []
        
        # Context information
        self.context_info = user_context.copy() if user_context else {}
        
        # Chat logging
        self.logging_level = os.getenv('MU2E_CHAT_ENABLE_LOGGING', 2) # 0=off, 1=at the end, 2=after each interaction
        self.log_dir = get_lof_dir()
        self.conversation_start_time = datetime.now()
        self.conversation_id = f"chat_{self.conversation_start_time.strftime('%Y%m%d_%H%M%S')}_{id(self)}"
        
        # Create log directory if it doesn't exist
        if self.logging_level > 0:
            os.makedirs(self.log_dir, exist_ok=True)
        
        #self.mcp_session: Optional[ClientSession] = None
        self.available_tools: List[Dict[str, Any]] = []
        
        # Base system prompt (will be enhanced with context)
        self.base_system_prompt =\
        """You are a helpful AI assistant for the Mu2e experiment with access to document search tools.

Use these tools proactively to find information that will help answer user questions. 
Ground your answers in information from the tools and be concise.

When searching:
- Use semantic search for conceptual questions about physics, procedures, or analysis
- Use fulltext_search for specific component names, numbers, or exact terms
- Always search recent documents first, then expand timeframe if needed

Use multiple tool calls when needed or ask the user for clarification.

Provide specific information rather than generic responses. If documents contain conflicting information, note the differences and cite both sources.

When answering based on search results, briefly explain what you searched for.

Always cite documents with their IDs and links using this format: 
[mu2e-docdb-12345](https://mu2e-docdb.fnal.gov/cgi-bin/sso/ShowDocument?docid=12345)"""

    async def _checkMCP(self):
        if self.mcp is None:
            await self.createMcp()

    def set_tool_use_callback(self, callback):
        """Set a callback function to be called when tools are used.
        
        Args:
            callback: Async function that takes (tool_name, arguments) as parameters
        """
        self._tool_use_callback = callback

    def _build_system_prompt(self, additional_context=None) -> str:
        """Build system prompt with current date/time and user context."""
        prompt = self.base_system_prompt
        
        # Add current date/time
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
        prompt += f"\n\nCurrent date and time: {current_time}"
        
        # Merge stored context with any additional context
        context = self.context_info.copy()
        if additional_context:
            context.update(additional_context)
        
        # Add context information
        if context.get('user_name'):
            prompt += f"\nUser: {context['user_name']}"
        if context.get('slack_channel_url'):
            prompt += f"\nSlack channel: {context['slack_channel_url']}"
                
        return prompt

    def _save_conversation_log(self):
        """Save conversation to JSON file"""
        if self.logging_level == 0 or not self.messages:
            return
            
        try:
            log_data = {
                "conversation_id": self.conversation_id,
                "start_time": self.conversation_start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "context_info": self.context_info,
                "system_message": self._build_system_prompt(),
                "messages": self.messages,
                "model": self.model,
                "base_url": self.base_url
            }
            
            log_file_path = os.path.join(self.log_dir, f"{self.conversation_id}.json")
            with open(log_file_path, 'w') as f:
                json.dump(log_data, f, indent=2)
                
            print(f"Conversation logged to: {log_file_path}")
            
        except Exception as e:
            print(f"Warning: Failed to save conversation log: {e}")

    async def cleanup(self):
        # Save conversation log before cleanup
        self._save_conversation_log()
        
        if self.mcp is not None:
            try:
                await self.mcp.close()
            except Exception as e:
                print(f"Warning: Error during MCP cleanup: {e}")
            finally:
                self.mcp = None

    async def createMcp(self):
        self.mcp = await MCPClient.create(self.mcp_server_url)

        tool_list = await self.mcp.list_tools()
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            }
            for tool in tool_list.tools
        ]

    async def health_check(self) -> Dict[str, Any]:
        """Check health of all services."""
        status = {
            "openai_api": {"status": "unknown", "url": self.base_url},
            "mcp_server": {"status": "unknown", "url": self.mcp_server_url},
            "overall": "unknown"
        }
        
        # Check OpenAI API
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url.rstrip('/v1')}/health", timeout=5) as resp:
                    if resp.status == 200:
                        status["openai_api"]["status"] = "healthy"
                    else:
                        status["openai_api"]["status"] = f"error_code_{resp.status}"
        except Exception as e:
            status["openai_api"]["status"] = f"unreachable: {str(e)}"
        
        # Check MCP server
        try:
            await self._checkMCP()
            if self.mcp._connected:
                status["mcp_server"]["status"] = "healthy"
            if self.mcp is None:
                status["mcp_server"]["status"] = "unreachable"
        except Exception as e:
            status["mcp_server"]["status"] = f"unreachable: {str(e)}"
        
        # Overall status
        if all(s["status"] == "healthy" for s in [status["openai_api"], status["mcp_server"]]):
            status["overall"] = "healthy"
        else:
            status["overall"] = "degraded"
        
        return status
        
    async def chat(self, user_message: str, user_context=None) -> str:
        """
        Send a message and get a response with automatic tool handling.
        
        Args:
            user_message: User's message            
        Returns:
            Assistant's response
        """
        
        # Add user message to conversation
        self.messages.append({"role": "user", "content": user_message})

        await self._checkMCP()
        
        # Prepare messages with dynamic system prompt
        system_prompt = self._build_system_prompt(user_context)
        full_messages = [
            {"role": "system", "content": system_prompt}
        ] + self.messages
        
        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                tools=self.tools if self.tools else None,
                tool_choice="auto" if self.tools else None
            )
            message = response.choices[0].message
            
            # Handle tool calls
            if message.tool_calls:
                
                # Add assistant message with tool calls
                self.messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                })
                
                # Execute each tool call
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    # Call MCP tool
                    print(f"USING TOOL: {tool_name} with {arguments}")
                    
                    # Notify about tool usage if callback is provided
                    if hasattr(self, '_tool_use_callback') and self._tool_use_callback:
                        await self._tool_use_callback(tool_name, arguments)
                    
                    try:
                        tool_result = await self.mcp.call_tool(tool_name, arguments)
                        content = tool_result.content[0].text if tool_result.content else "No content"
                    except Exception as e:
                        content = f"Tool error: {str(e)}"
                    
                    # Add tool result to conversation
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": content
                    })
                
                # Get final response after tool execution
                final_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": system_prompt}] + self.messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                
                final_content = final_response.choices[0].message.content or ""
                self.messages.append({"role": "assistant", "content": final_content})
                
                if self.logging_level >= 3:
                    self._save_conversation_log()
                return final_content
                
            else:
                # No tool calls, regular response
                content = message.content or ""
                self.messages.append({"role": "assistant", "content": content})
                
                if self.logging_level >= 2:
                    self._save_conversation_log()
                return content
                
        except Exception as e:
            error_msg = f"Chat error: {str(e)}"
            import traceback
            error_msg += f"\nBacktrace:\n{traceback.format_exc()}"
            print(error_msg)
            return error_msg

    def clear_conversation(self):
        """Clear conversation history."""
        self.messages = []

    def get_conversation(self) -> List[Dict[str, Any]]:
        """Get conversation history."""
        return self.messages.copy()
