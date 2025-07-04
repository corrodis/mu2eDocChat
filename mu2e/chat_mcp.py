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
from openai import InternalServerError, APIError
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from contextlib import AsyncExitStack
import aiohttp
import subprocess
from dotenv import load_dotenv
from .utils import get_log_dir, get_max_context
from .tools import getOpenAIClient, token_count
from .agent_tasks import summarize_search_results

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
            # Don't print connection messages during health checks to reduce noise
            return server
        except (Exception, asyncio.CancelledError) as e:
            # Clean up properly on failure
            if hasattr(server, '_exit_stack') and server._exit_stack is not None:
                try:
                    await server._exit_stack.aclose()
                except:
                    pass
                server._exit_stack = None
            server._connected = False
            server.mcp_session = None
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
        max_tokens: int = 8000,
        mcp_server_url: str = None,
        mcp_timeout_seconds: int = 10,
        api_key: str = None,
        user_context: dict = None,
        recreate_mcp_per_message: bool = False,
        use_summarization_agent: bool = True
    ):
        # Load from environment with defaults (chat-specific variables)
        load_dotenv()
        self.base_url = base_url or os.getenv('MU2E_CHAT_BASE_URL', 'http://localhost:55019/v1')
        self.model = model or os.getenv('MU2E_CHAT_MODEL', 'argo:gpt-4o')
        self.mcp_server_url = mcp_server_url or os.getenv('MU2E_CHAT_MCP_URL', 'http://localhost:1223/mcp/')
        #self.api_key = api_key or os.getenv('MU2E_CHAT_API_KEY', os.getenv('OPENAI_API_KEY', 'whatever+random'))
        
        self.client = getOpenAIClient() 
        self.mcp = None
        self.tools = []
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.recreate_mcp_per_message = recreate_mcp_per_message
        self.use_summarization_agent = use_summarization_agent

        # Conversation history
        self.messages: List[Dict[str, Any]] = []
        
        # Context information
        self.context_info = user_context.copy() if user_context else {}
        
        # Chat logging
        self.logging_level = int(os.getenv('MU2E_CHAT_ENABLE_LOGGING', 1)) # 0=off, 1=at the end, 2=after each interaction
        self.log_dir = get_log_dir()
        self.conversation_start_time = datetime.now()
        self.conversation_id = f"chat_{self.conversation_start_time.strftime('%Y%m%d_%H%M%S')}_{id(self)}"
        
        # Create log directory if it doesn't exist
        if self.logging_level > 0:
            os.makedirs(self.log_dir, exist_ok=True)
        
        #self.mcp_session: Optional[ClientSession] = None
        self.available_tools: List[Dict[str, Any]] = []
        
        # Base system prompt (will be enhanced with context)
        self.base_system_prompt =\
        """You are a helpful AI assistant for the Mu2e experiment with access to multiple document search tools.

AVAILABLE TOOLS:
- docdb_search: Semantic search for concepts, topics, and meaning-based queries
- docdb_fulltext: Keyword/exact text search for specific terms or phrases  
- docdb_list: Browse recent documents (use include_documents=false for fast title-only browsing, or include_documents=true for full content)
- docdb_get: Retrieve complete document content by ID when full context is needed for detailed analysis

SEARCH STRATEGY:
Use these tools proactively and strategically. For comprehensive answers, perform multi-step research by chaining multiple searches. Start with semantic search (docdb_search) for topic-based queries, use fulltext search (docdb_fulltext) for specific terms. Only use docdb_list when explicitly asked about recent document activity (e.g., "what documents were added in the last X days") - use include_documents=false for faster response when browsing titles and abstracts. Use docdb_get when you need complete document context for detailed analysis or when search results only provide partial information.

RESPONSE GUIDELINES:
- Ground all answers in actual tool responses from the conversation
- Be concise but thorough - large documents may be auto-summarized while preserving key details
- Make additional tool calls when needed for supplementary information
- Ask for clarification when questions are ambiguous
- Provide specific information rather than generic responses
- If documents contain conflicting information, note differences and cite both sources
- If you make an error or the user corrects you, carefully review available information before responding

CITATIONS:
Always cite documents with their IDs and links using this format: 
[mu2e-docdb-12345](https://mu2e-docdb.fnal.gov/cgi-bin/sso/ShowDocument?docid=12345)"""

    async def _checkMCP(self):
        if self.mcp is None or self.recreate_mcp_per_message:
            # Clean up existing MCP if recreating
            #if self.mcp is not None and self.recreate_mcp_per_message:
            #    try:
            #        await self.mcp.close()
            #    except:
            #        pass
            await self.createMcp()

    def set_status_callback(self, callback):
        """Set a callback function to communicate status updates to the user.
        
        Args:
            callback: Async function that takes (message, metadata) as parameters
        """
        self._status_callback = callback

    async def _call_openai_with_retry(self, **kwargs):
        """Call OpenAI API with retry logic for 500/503 errors."""
        max_retries = 1
        base_delay = 60
        
        # Calculate token count for the request
        messages = kwargs.get('messages', [])
        request_tokens = token_count(messages) if messages else 0
        
        # Check if context exceeds maximum limit
        max_context = get_max_context()
        if request_tokens > max_context:
            raise ValueError(f"Context too large: {request_tokens} tokens exceeds maximum of {max_context} tokens. Please start a new chat.")
        
        for attempt in range(max_retries + 1):
            try:
                return self.client.chat.completions.create(**kwargs)
                
            except (InternalServerError, APIError) as e:
                error_code = getattr(e, 'status_code', None)
                
                if error_code in [500, 503] and attempt < max_retries:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    
                    # Notify user about the retry with token count
                    if hasattr(self, '_status_callback') and self._status_callback:
                        await self._status_callback(f"Server error ({request_tokens} tokens, attempt {attempt + 1}/{max_retries + 1}). Retrying in {delay}s...", {
                            "type": "system_warning",
                            "attempt": attempt + 1,
                            "max_attempts": max_retries + 1,
                            "delay": delay,
                            "request_tokens": request_tokens
                        })
                    
                    print(f"OpenAI API error (attempt {attempt + 1}, {request_tokens} tokens): {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Max retries reached or non-retryable error
                    print(f"OpenAI API error (final failure, {request_tokens} tokens): {e}")
                    raise e
            
            except Exception as e:
                # Non-retryable error
                print(f"OpenAI API non-retryable error ({request_tokens} tokens): {e}")
                raise e


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
        prompt += "\n\n Context: " + json.dumps(context, indent=2)
                
        return prompt
    
    async def _update_context_callback(self):
        """Send context update callback if available."""
        if hasattr(self, '_status_callback') and self._status_callback:
            context_tokens = token_count([{"role": "system", "content": self._build_system_prompt()}] + self.messages)
            try:
                await self._status_callback("", {
                    "type": "context_update",
                    "tokens": context_tokens
                })
            except Exception as e:
                print(f"Error sending context update: {e}")

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

        if self.mcp._connected:
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
                if self.recreate_mcp_per_message:
                    await self.mcp.close()
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
        
    async def chat(self, user_message: str = None, user_context=None, _recursion_depth=0) -> str:
        """
        Send a message and get a response with automatic tool handling.
        
        Args:
            user_message: User's message (None if no new user message should be added)
            user_context: Additional context for this message
            _recursion_depth: Internal recursion tracking
        Returns:
            Assistant's response
        """
        
        # Maximum recursion depth to prevent infinite loops
        MAX_RECURSION_DEPTH =10 
        
        # Add user message to conversation if provided
        if user_message is not None:
            self.messages.append({"role": "user", "content": user_message})
            await self._update_context_callback()

        await self._checkMCP()
        
        # Prepare messages with dynamic system prompt
        system_prompt = self._build_system_prompt(user_context)
        full_messages = [
            {"role": "system", "content": system_prompt}
        ] + self.messages
        
        try:
            # Call OpenAI API with retry logic
            response = await self._call_openai_with_retry(
                model=self.model,
                messages=full_messages,
                temperature=self.temperature,
                #max_tokens=self.max_tokens,
                tools=self.tools if self.tools else None,
                tool_choice="auto" if self.tools else None,
                parallel_tool_calls=True
            )
            message = response.choices[0].message
            
            # Handle tool calls
            if message.tool_calls:
                
                # Add assistant message with tool calls
                # anthropic
                if any(model_name in self.model for model_name in ["claude", "sonnet", "opus"]):
                    content = []
                    content.extend([
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.function.name,
                            "input": json.loads(tc.function.arguments)
                        }
                        for tc in message.tool_calls
                    ])
                    self.messages.append({
                        "role": "assistant",
                        "content": content
                    })
                    await self._update_context_callback()
                else: # openAI
                    self.messages.append({
                        "role": "assistant",
                        "content": message.content or '',
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
                    await self._update_context_callback()
                
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
                    if hasattr(self, '_status_callback') and self._status_callback:
                        await self._status_callback(f"using '{tool_name}' with '{arguments}'", {
                            "type": "tool_start",
                            "tool_name": tool_name,
                            "arguments": arguments
                        })
                    
                    try:
                        tool_result = await self.mcp.call_tool(tool_name, arguments)
                        content = tool_result.content[0].text if tool_result.content else "No content"
                    except Exception as e:
                        content = f"Tool error: {str(e)}"
                    
                    token_count_ = token_count(content)
                    print(f"TOOL USE DONE: {token_count_} tokens: {content[:50]}")
                    
                    # Notify about tool results
                    if hasattr(self, '_status_callback') and self._status_callback:
                        await self._status_callback(f"Found {token_count_} tokens ({len(content)} chars)  of content", {
                            "type": "tool_result",
                            "tool_name": tool_name,
                            "tokens": token_count_
                        })
                    
                    # Apply summarization if agent is enabled and it's a search/list tool with sufficient content
                    if (self.use_summarization_agent and 
                        any(search_tool in tool_name for search_tool in ["search", "fulltext_search", "docdb_search", "list", "docdb_list"]) and
                        token_count_ >= 500):
                        
                        # Build conversation context from natural conversation messages only
                        conversation_messages = []
                        for msg in self.messages:
                            # Include user messages with string content (no tool results)
                            if (msg["role"] == "user" and 
                                isinstance(msg["content"], str) and 
                                "type" not in msg):
                                conversation_messages.append(f"User: {msg['content']}")
                            # Include assistant messages with string content
                            elif (msg["role"] == "assistant" and 
                                  isinstance(msg["content"], str) and 
                                  "tool_calls" not in msg):
                                conversation_messages.append(f"Assistant: {msg['content']}")
                        
                        conversation_context = " | ".join(conversation_messages)
                        print("DEBUG conversation_context:", conversation_context)
                        
                        # Notify about agent usage
                        if hasattr(self, '_status_callback') and self._status_callback:
                            await self._status_callback("Running agents to summariz results...", {
                                "type": "agent_start",
                                "agent": "DocumentSummarizerAgent",
                                "task": "summarize_search_results",
                                "original_tokens": token_count_
                            })
                        
                        content = await summarize_search_results(content, conversation_context)
                        
                        # Notify about agent completion
                        if hasattr(self, '_status_callback') and self._status_callback:
                            new_token_count = token_count(content)
                            await self._status_callback(f"Summarization complete: {token_count_} → {new_token_count} tokens", {
                                "type": "agent_complete",
                                "agent": "DocumentSummarizerAgent",
                                "original_tokens": token_count_,
                                "new_tokens": new_token_count,
                                "tokens_saved": token_count_ - new_token_count
                            })
                    # if anthropic
                    if any(model_name in self.model for model_name in ["claude", "sonnet", "opus"]):
                        self.messages.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": tool_call.id,
                                "content": content
                            }]
                        })
                        await self._update_context_callback()
                    else:
                        # Add openAI tool result to conversation
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": content
                        })
                        await self._update_context_callback()
                               
                if self.recreate_mcp_per_message:
                    await self.mcp.close()

                # Check if we should recurse to allow more tool calls
                if _recursion_depth < MAX_RECURSION_DEPTH:
                    # Recursively call chat to see if LLM wants more tool calls
                    return await self.chat(user_message=None, user_context=user_context, _recursion_depth=_recursion_depth + 1)

                print("DEBUG send tool respond to LLM with ", token_count([{"role": "system", "content": system_prompt}] + self.messages), "tokens.")
                # Get final response after tool execution (or if max recursion depth reached)
                final_response = await self._call_openai_with_retry(
                    model=self.model,
                    messages=[{"role": "system", "content": system_prompt}] + self.messages,
                    temperature=self.temperature,
                    #max_tokens=self.max_tokens
                )

                print("DEBUG send tool respons to LLM - DONE")
                
                final_content = final_response.choices[0].message.content or ""
                self.messages.append({"role": "assistant", "content": final_content})
                await self._update_context_callback()
                
                if self.logging_level >= 3:
                    self._save_conversation_log()
                return final_content
                
            else:
                # No tool calls, regular response
                content = message.content or ""
                self.messages.append({"role": "assistant", "content": content})
                await self._update_context_callback()
                
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
