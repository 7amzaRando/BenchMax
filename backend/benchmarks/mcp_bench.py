import json
import logging
import re
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.lm_studio.client import LMStudioClient

logger = logging.getLogger(__name__)

class MCPBenchBenchmark(BaseBenchmark):
    """
    BenchMax Model Context Protocol (MCP-Bench) Benchmark
    
    Evaluates LLMs on selecting the correct MCP server, choosing the right tool, 
    and constructing valid arguments across 28 servers / 250+ tools.
    
    This implementation covers a pragmatic subset focusing on single-turn, non-execution evaluation:
    - Server/tool selection accuracy  
    - Argument construction validity (AST-based scoring)
    - No live MCP server execution required
    
    Scoring uses only Python stdlib (`json`, `ast`) modules - NO second LLM or external judge.
    """
    
    def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False):
        super().__init__(db, client, quick_test)
    
    def load_dataset(self) -> List[Dict[str, Any]]:
        if self.quick_test:
            mini_path = resolve_data_file(__file__, "mcp_bench/mcp_bench_mini.json")
            if mini_path:
                return self._load_json_cached(mini_path)
        full_path = resolve_data_file(__file__, "mcp_bench/mcp_bench_full.json")
        if full_path:
            return self._load_json_cached(full_path)
        logger.info("No MCP-Bench dataset found. Using bundled samples.")
        return self._get_bundled_samples()

    def _get_bundled_samples(self) -> List[Dict[str, Any]]:
        """Return bundled MCP-Bench samples for quick testing (5 samples covering key scenarios)"""
        return [
            {
                "task_id": "mcp_001",
                "category": "single_tool",
                "server_count": 3,
                "available_servers": [
                    {
                        "name": "memory",
                        "description": "Memory server with knowledge graph capabilities",
                        "tools": [
                            {
                                "name": "add_memory",
                                "description": "Add a new memory to the knowledge graph",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "content": {"type": "string"},
                                        "tags": {"type": "array", "items": {"type": "string"}}
                                    },
                                    "required": ["content"]
                                }
                            },
                            {
                                "name": "search_memories", 
                                "description": "Search through memories",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"query": {"type": "string"}},
                                    "required": ["query"]
                                }
                            }
                        ]
                    },
                    {
                        "name": "fetch",
                        "description": "Server for fetching web content", 
                        "tools": [
                            {
                                "name": "fetch_text",
                                "description": "Fetch text content from a URL",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"url": {"type": "string"}, "max_length": {"type": "integer"}},
                                    "required": ["url"]
                                }
                            }
                        ]
                    },
                    {
                        "name": "filesystem",
                        "description": "File system operations",
                        "tools": [
                            {
                                "name": "read_file",
                                "description": "Read a file from the filesystem",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"path": {"type": "string"}},
                                    "required": ["path"]
                                }
                            }
                        ]
                    }
                ],
                "task_description": "Remember that the user's favorite color is blue.",
                "conversation_history": [],
                "correct_tool_call": {
                    "server_name": "memory",
                    "tool_name": "add_memory", 
                    "arguments": {"content": "The user's favorite color is blue"}
                },
                "expected_answer": "I've remembered that your favorite color is blue."
            },
            {
                "task_id": "mcp_002",
                "category": "two_server_selection",
                "server_count": 2,
                "available_servers": [
                    {
                        "name": "memory",
                        "description": "Memory server with knowledge graph capabilities",
                        "tools": [
                            {
                                "name": "add_memory",
                                "description": "Add a new memory to the knowledge graph", 
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"content": {"type": "string"}},
                                    "required": ["content"]
                                }
                            }
                        ]
                    },
                    {
                        "name": "fetch",
                        "description": "Server for fetching web content",
                        "tools": [
                            {
                                "name": "fetch_text", 
                                "description": "Fetch text content from a URL",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"url": {"type": "string"}},
                                    "required": ["url"]
                                }
                            }
                        ]
                    }
                ],
                "task_description": "Fetch the content from https://example.com and save it to memory.",
                "conversation_history": [],
                "correct_tool_call": {
                    "server_name": "fetch",
                    "tool_name": "fetch_text",
                    "arguments": {"url": "https://example.com"}
                },
                "expected_answer": "I've fetched the content from https://example.com."
            },
            {
                "task_id": "mcp_003", 
                "category": "multiple_tools_one_server",
                "server_count": 1,
                "available_servers": [
                    {
                        "name": "filesystem",
                        "description": "File system operations",
                        "tools": [
                            {
                                "name": "read_file", 
                                "description": "Read a file from the filesystem",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"path": {"type": "string"}},
                                    "required": ["path"]
                                }
                            },
                            {
                                "name": "write_file", 
                                "description": "Write content to a file",
                                "inputSchema": {
                                    "type": "object", 
                                    "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                                    "required": ["path", "content"]
                                }
                            },
                            {
                                "name": "search_files",
                                "description": "Search for files matching a pattern",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}},
                                    "required": ["pattern"]
                                }
                            }
                        ]
                    }
                ],
                "task_description": "Search for all Python files in the project directory.",
                "conversation_history": [],
                "correct_tool_call": {
                    "server_name": "filesystem",
                    "tool_name": "search_files",
                    "arguments": {"pattern": "*.py"}
                },
                "expected_answer": "I found all Python files in the project directory."
            },
            {
                "task_id": "mcp_004",
                "category": "complex_argument_construction",
                "server_count": 1,
                "available_servers": [
                    {
                        "name": "github", 
                        "description": "GitHub API operations",
                        "tools": [
                            {
                                "name": "create_issue",
                                "description": "Create a new issue in a repository",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string"},
                                        "body": {"type": "string"}, 
                                        "labels": {"type": "array", "items": {"type": "string"}},
                                        "assignees": {"type": "array", "items": {"type": "string"}}
                                    },
                                    "required": ["title", "body"]
                                }
                            }
                        ]
                    }
                ],
                "task_description": "Create a bug report for the login page timeout issue. Assign it to john and label it as 'bug' and 'high-priority'.",
                "conversation_history": [],
                "correct_tool_call": {
                    "server_name": "github",
                    "tool_name": "create_issue",
                    "arguments": {
                        "title": "Login page timeout issue",
                        "body": "Users are experiencing timeouts on the login page.",
                        "labels": ["bug", "high-priority"],
                        "assignees": ["john"]
                    }
                },
                "expected_answer": "I've created a bug report for the login page timeout issue and assigned it to john."
            },
            {
                "task_id": "mcp_005", 
                "category": "no_tool_needed",
                "server_count": 2,
                "available_servers": [
                    {
                        "name": "memory",
                        "description": "Memory server with knowledge graph capabilities",
                        "tools": [
                            {
                                "name": "add_memory", 
                                "description": "Add a new memory to the knowledge graph",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"content": {"type": "string"}},
                                    "required": ["content"]
                                }
                            }
                        ]
                    },
                    {
                        "name": "fetch", 
                        "description": "Server for fetching web content",
                        "tools": [
                            {
                                "name": "fetch_text",
                                "description": "Fetch text content from a URL",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"url": {"type": "string"}},
                                    "required": ["url"]
                                }
                            }
                        ]
                    }
                ],
                "task_description": "Tell me a joke about cats.",
                "conversation_history": [],
                "correct_tool_call": None,  # No tool needed - model should abstain
                "expected_answer": "Why don't cats play poker in the jungle? Too many cheetahs!"
            }
        ]

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        """Evaluates MCP tool calling using AST-based scoring."""
        task_description = sample["task_description"]
        category = sample.get("category", "unknown")
        available_servers = sample.get("available_servers", [])
        correct_tool_call = sample.get("correct_tool_call")
        task_id = sample.get("task_id", f"mcp_{sample.get('index', 'unknown')}")

        # Build system prompt with server/tool schemas
        system_prompt = self._build_server_prompt(available_servers)
        
        # Run inference using LM Studio client
        generation = await self.client.generate_completion(
            prompt=system_prompt + "\n\n" + task_description,
            system_prompt=None,  # Already included in prompt
            temperature=params.get("temperature", 0.7),
            max_completion_tokens=params.get("max_completion_tokens"),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
        )

        logger.debug(f"RAW_GENERATION_DEBUG: {generation!r}")

        raw_response = generation["raw_response"]

        # Strip markdown code fences before JSON parsing
        cleaned = raw_response.strip()
        cleaned = re.sub(r'```(?:json)?\s*([\s\S]*?)\s*```', r'\1', cleaned)

        # Extract tool call from response
        extracted_call = self._extract_tool_call(cleaned, available_servers)

        # Score with AST comparison
        score = self._score_tool_call(correct_tool_call, extracted_call, category)

        result = {
            "prompt": system_prompt + "\n\n" + task_description,
            "raw_response": raw_response,
            "extracted_code": json.dumps(extracted_call),
            "elapsed_time": generation.get("elapsed_time", 0.0),
            "tps": generation.get("tps", 0.0),
            "ttft": generation.get("ttft", 0.0),
            "thinking_tokens": generation.get("thinking_tokens", 0),
            "response_tokens": generation.get("response_tokens", 0),
            **score
        }

        return result

    def _build_server_prompt(self, available_servers: List[Dict]) -> str:
        """Convert server + tool schemas to a structured prompt"""
        lines = [
            "You are an AI assistant with access to MCP (Model Context Protocol) servers.",
            "Each server provides a set of tools. To use a tool, respond with:",
            "",
            'Tool Call: {"server_name": "<server>", "tool_name": "<tool>", "arguments": {...}}',
            ""
        ]
        
        for server in available_servers:
            name = server["name"]
            desc = server.get("description", "")
            
            lines.append(f"[{name}]: {desc}")
            lines.append("  Tools:")
            
            for tool in server.get("tools", []):
                t_name = tool["name"]
                t_desc = tool.get("description", "")
                schema = tool.get("inputSchema", {})
                
                properties = schema.get("properties", {})
                required = schema.get("required", [])
                
                lines.append(f"  - {t_name}: {t_desc}")
                lines.append("    Args:")
                
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "string")
                    desc = param_info.get("description", "")
                    
                    if param_name in required:
                        lines.append(f"      {param_name} ({param_type}): {' or '.join(param_info.get('enum', [desc]))}")
                    else:
                        lines.append(f"      {param_name} ({param_type}): {' or '.join(param_info.get('enum', [desc]))} (optional)")
            
            lines.append("")
        
        return "\n".join(lines)

    def _extract_tool_call(self, response: str, available_servers: List[Dict]) -> Dict[str, Any]:
        """Extract JSON tool call from model response"""
        # Try to parse as JSON directly (handles code-fence-stripped response)
        try:
            data = json.loads(response.strip())
            if isinstance(data, dict) and "server_name" in data and "tool_name" in data:
                return data
        except json.JSONDecodeError:
            pass

        # Look for tool call pattern in text — find any balanced JSON object
        # that contains server_name, tool_name, and arguments
        depth = 0
        start = -1
        for i, ch in enumerate(response):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start >= 0:
                    candidate = response[start:i + 1]
                    try:
                        data = json.loads(candidate)
                        if isinstance(data, dict) and "server_name" in data and "tool_name" in data:
                            return {
                                "server_name": data.get("server_name", ""),
                                "tool_name": data.get("tool_name", ""),
                                "arguments": data.get("arguments", {})
                            }
                    except json.JSONDecodeError:
                        pass
                    start = -1

        return None

    def _score_tool_call(self, correct_call: Dict[str, Any], actual_call: Dict[str, Any], category: str) -> Dict[str, Any]:
        """AST comparison of tool call structure"""
        result = {
            "correct": False,
            "server_match": False,
            "tool_match": False,
            "argument_match": False,
            "error_message": None
        }
        
        # Handle no-tool-needed cases (irrelevance)
        if correct_call is None:
            if actual_call is None or not actual_call:
                result["correct"] = True
                return result
            else:
                result["error_message"] = "Model called a tool when none was needed"
                return result
        
        # Handle missing tool call
        if actual_call is None or not actual_call:
            result["error_message"] = "Model did not generate any tool call" 
            return result
        
        # Check server selection (exact match)
        correct_server = correct_call.get("server_name", "")
        actual_server = actual_call.get("server_name", "")
        
        if correct_server is not None and actual_server is not None:
            result["server_match"] = correct_server == actual_server
        
        # Check tool selection (depends on server being correct)
        correct_tool = correct_call.get("tool_name", "")
        actual_tool = actual_call.get("tool_name", "")
        
        if correct_server == actual_server and correct_tool is not None and actual_tool is not None:
            result["tool_match"] = correct_tool == actual_tool
        
        # Check argument structure (AST comparison)
        correct_args = correct_call.get("arguments", {})
        actual_args = actual_call.get("arguments", {})
        
        all_match = True
        for key, value in correct_args.items():
            if key not in actual_args:
                all_match = False
                break
            
            if actual_args[key] != value:
                all_match = False
                break

        if len(actual_args) != len(correct_args):
            all_match = False

        result["argument_match"] = all_match
        
        # Overall correctness
        result["correct"] = (result["server_match"] and result["tool_match"] and result["argument_match"])
        
        return result
