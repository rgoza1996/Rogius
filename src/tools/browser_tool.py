"""
Browser Tool - Web automation for Rogius using Playwright.

Encapsulates all browser automation logic including:
- Cross-browser web navigation (Chromium, Firefox, WebKit)
- DOM-based interaction (click, fill, select, wait, extract)
- Screenshot capture after every operation
- Persistent sessions with automatic cleanup
- Session management (open/close/reuse)
"""

import os
import time
import tempfile
import fnmatch
from typing import Dict, Optional, Any, List
from .tool_interface import Tool, Action, ActionType, ToolResult
from .tool_registry import tool

# Playwright import with graceful fallback
try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
except ImportError:
    async_playwright = None
    Page = None
    Browser = None
    BrowserContext = None


@tool(ActionType.WEB_CRAWL)
class BrowserTool(Tool):
    """
    Tool for web automation using Playwright.
    
    Features:
    - DOM-based interaction (NOT OCR/pixel-based)
    - Persistent sessions (session_id tracking)
    - Headed mode by default (visible browser)
    - Screenshot after every operation
    - Automatic cleanup of old screenshots
    - Operation types: goto, click, fill, select, wait, extract, screenshot, close
    
    The browser instance persists across multiple actions until explicitly closed.
    """
    
    # Session storage: session_id -> {playwright, browser, context, page}
    _sessions: Dict[str, Dict[str, Any]] = {}
    
    @property
    def action_type(self) -> ActionType:
        return ActionType.WEB_CRAWL
    
    async def execute(self, action: Action, env_context: dict) -> ToolResult:
        """
        Execute browser automation actions.
        
        Args:
            action: Action with payload containing:
                - session_id: Optional existing session to reuse
                - url: Starting URL
                - operations: List of operations to perform
                - headless: Whether to run in headless mode (default: False)
                - slow_mo: Delay between actions in ms (default: 500)
                - browser_type: "chromium", "firefox", or "webkit" (default: chromium)
            env_context: Environment context dict
            
        Returns:
            ToolResult with screenshots, extracted data, and session info
        """
        # Check if Playwright is available
        if async_playwright is None:
            return ToolResult(
                success=False,
                output="",
                artifacts={},
                error="Playwright not installed. Run: pip install playwright && playwright install chromium"
            )
        
        payload = action.payload
        session_id = payload.get("session_id")
        url = payload.get("url")
        operations = payload.get("operations", [])
        headless = payload.get("headless", False)  # Default: visible browser
        slow_mo = payload.get("slow_mo", 500)
        browser_type = payload.get("browser_type", "chromium")
        
        screenshots: List[str] = []
        extracted_data: Dict[str, Any] = {}
        current_url = None
        
        try:
            # Get or create session
            if session_id and session_id in self._sessions:
                session = self._sessions[session_id]
                page = session["page"]
                print(f"[BrowserTool] Reusing session: {session_id}")
            else:
                # Create new session
                session_id = session_id or f"browser_{int(time.time())}"
                print(f"[BrowserTool] Creating new session: {session_id}")
                
                playwright = await async_playwright().start()
                
                # Launch browser based on type
                if browser_type == "firefox":
                    browser = await playwright.firefox.launch(
                        headless=headless,
                        slow_mo=slow_mo
                    )
                elif browser_type == "webkit":
                    browser = await playwright.webkit.launch(
                        headless=headless,
                        slow_mo=slow_mo
                    )
                else:  # default chromium
                    browser = await playwright.chromium.launch(
                        headless=headless,
                        slow_mo=slow_mo
                    )
                
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    record_video_dir=tempfile.gettempdir() if not headless else None
                )
                page = await context.new_page()
                
                self._sessions[session_id] = {
                    "playwright": playwright,
                    "browser": browser,
                    "context": context,
                    "page": page,
                    "created_at": time.time()
                }
                session = self._sessions[session_id]
            
            # Navigate to initial URL if provided
            if url:
                print(f"[BrowserTool] Navigating to: {url}")
                await page.goto(url, wait_until="networkidle")
                current_url = page.url
                
                # Initial screenshot
                screenshot_path = await self._capture_screenshot(page, session_id, "initial")
                screenshots.append(screenshot_path)
                print(f"[BrowserTool] Captured initial screenshot: {screenshot_path}")
            
            # Execute operations
            for idx, op in enumerate(operations):
                op_type = op.get("type")
                print(f"[BrowserTool] Operation {idx + 1}/{len(operations)}: {op_type}")
                
                try:
                    if op_type == "goto":
                        target_url = op.get("url", url)
                        await page.goto(target_url, wait_until="networkidle")
                        current_url = page.url
                        
                    elif op_type == "click":
                        selector = op.get("selector")
                        await page.click(selector)
                        
                    elif op_type == "fill":
                        selector = op.get("selector")
                        value = op.get("value", "")
                        await page.fill(selector, value)
                        
                    elif op_type == "type":
                        selector = op.get("selector")
                        value = op.get("value", "")
                        delay = op.get("delay", 50)  # ms between keystrokes
                        await page.type(selector, value, delay=delay)
                        
                    elif op_type == "select":
                        selector = op.get("selector")
                        value = op.get("value")
                        label = op.get("label")
                        index = op.get("index")
                        
                        if value:
                            await page.select_option(selector, value=value)
                        elif label:
                            await page.select_option(selector, label=label)
                        elif index is not None:
                            await page.select_option(selector, index=index)
                            
                    elif op_type == "wait":
                        selector = op.get("selector")
                        timeout = op.get("timeout", 5000)
                        state = op.get("state", "visible")  # visible, hidden, attached, detached
                        await page.wait_for_selector(selector, state=state, timeout=timeout)
                        
                    elif op_type == "wait_for_load":
                        wait_until = op.get("wait_until", "networkidle")
                        timeout = op.get("timeout", 30000)
                        await page.wait_for_load_state(wait_until, timeout=timeout)
                        
                    elif op_type == "extract":
                        selector = op.get("selector")
                        attribute = op.get("attribute", "text")  # text, href, src, value, etc.
                        limit = op.get("limit", 10)
                        name = op.get("as", f"extract_{idx}")
                        
                        elements = await page.query_selector_all(selector)
                        data = []
                        for el in elements[:limit]:
                            if attribute == "text":
                                text = await el.inner_text()
                            elif attribute == "inner_html":
                                text = await el.inner_html()
                            elif attribute == "outer_html":
                                text = await el.outer_html()
                            else:
                                text = await el.get_attribute(attribute)
                            
                            if text:
                                data.append(text.strip())
                        
                        extracted_data[name] = data
                        print(f"[BrowserTool] Extracted {len(data)} items as '{name}'")
                        
                    elif op_type == "screenshot":
                        name = op.get("name", f"screenshot_{idx}")
                        screenshot_path = await self._capture_screenshot(page, session_id, name)
                        screenshots.append(screenshot_path)
                        print(f"[BrowserTool] Captured screenshot: {screenshot_path}")
                        
                    elif op_type == "scroll":
                        direction = op.get("direction", "down")
                        amount = op.get("amount", 500)
                        selector = op.get("selector")
                        
                        if selector:
                            element = await page.query_selector(selector)
                            if element:
                                await element.scroll_into_view_if_needed()
                        else:
                            if direction == "down":
                                await page.evaluate(f"window.scrollBy(0, {amount})")
                            elif direction == "up":
                                await page.evaluate(f"window.scrollBy(0, -{amount})")
                            elif direction == "bottom":
                                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            elif direction == "top":
                                await page.evaluate("window.scrollTo(0, 0)")
                                
                    elif op_type == "hover":
                        selector = op.get("selector")
                        await page.hover(selector)
                        
                    elif op_type == "press":
                        key = op.get("key", "Enter")
                        selector = op.get("selector")
                        if selector:
                            await page.press(selector, key)
                        else:
                            await page.keyboard.press(key)
                            
                    elif op_type == "evaluate":
                        script = op.get("script", "")
                        arg = op.get("arg")
                        result = await page.evaluate(script, arg)
                        extracted_data[f"eval_result_{idx}"] = str(result)
                        
                    elif op_type == "close":
                        await self._close_session(session_id)
                        print(f"[BrowserTool] Closed session: {session_id}")
                        break
                        
                    else:
                        print(f"[BrowserTool] Unknown operation type: {op_type}")
                        
                except Exception as op_error:
                    print(f"[BrowserTool] Operation {idx} failed: {op_error}")
                    # Capture error screenshot
                    error_path = await self._capture_screenshot(page, session_id, f"error_op_{idx}")
                    screenshots.append(error_path)
                    
                    # Decide whether to continue or abort based on operation
                    if op.get("critical", True):
                        raise op_error
                    else:
                        print(f"[BrowserTool] Continuing despite error (non-critical)")
                
                # Screenshot after every operation
                if op_type != "close":
                    after_path = await self._capture_screenshot(page, session_id, f"after_op_{idx}")
                    screenshots.append(after_path)
                
                # Update current URL
                if op_type != "close":
                    try:
                        current_url = page.url
                    except:
                        pass
            
            # Cleanup old screenshots (keep only last 50 per session)
            self._cleanup_old_screenshots(session_id, keep=50)
            
            # Build success result
            output_text = f"Browser session {session_id}: {len(operations)} operations completed"
            if extracted_data:
                output_text += f", extracted {len(extracted_data)} data sets"
            
            return ToolResult(
                success=True,
                output=output_text,
                artifacts={
                    "session_id": session_id,
                    "screenshots": screenshots,
                    "extracted_data": extracted_data,
                    "url": current_url,
                    "operations_completed": len(operations)
                }
            )
            
        except Exception as e:
            # Capture error screenshot if page exists
            error_screenshot = None
            if 'page' in locals() and page:
                try:
                    error_screenshot = await self._capture_screenshot(page, session_id, "error")
                    screenshots.append(error_screenshot)
                except:
                    pass
            
            error_msg = f"Browser operation failed: {str(e)}"
            print(f"[BrowserTool] {error_msg}")
            
            return ToolResult(
                success=False,
                output=error_msg,
                artifacts={
                    "session_id": session_id,
                    "screenshots": screenshots,
                    "extracted_data": extracted_data,
                    "url": current_url if current_url else None,
                    "error_type": type(e).__name__
                },
                error=error_msg
            )
    
    async def _capture_screenshot(self, page: Page, session_id: str, name: str) -> str:
        """
        Capture screenshot and return path.
        
        Args:
            page: Playwright page object
            session_id: Session identifier
            name: Screenshot name identifier
            
        Returns:
            Path to saved screenshot file
        """
        timestamp = int(time.time() * 1000)  # Milliseconds for uniqueness
        filename = f"browser_{session_id}_{name}_{timestamp}.png"
        path = os.path.join(tempfile.gettempdir(), filename)
        
        await page.screenshot(path=path, full_page=True)
        return path
    
    def _cleanup_old_screenshots(self, session_id: str, keep: int = 50):
        """
        Remove old screenshots, keeping only the most recent N.
        
        Args:
            session_id: Session to cleanup screenshots for
            keep: Number of recent screenshots to preserve
        """
        pattern = f"browser_{session_id}_*.png"
        temp_dir = tempfile.gettempdir()
        
        try:
            files = [
                f for f in os.listdir(temp_dir)
                if fnmatch.fnmatch(f, pattern)
            ]
            
            # Sort by modification time (newest first)
            files.sort(
                key=lambda f: os.path.getmtime(os.path.join(temp_dir, f)),
                reverse=True
            )
            
            # Delete old files
            for old_file in files[keep:]:
                try:
                    os.remove(os.path.join(temp_dir, old_file))
                    print(f"[BrowserTool] Cleaned up old screenshot: {old_file}")
                except Exception as e:
                    print(f"[BrowserTool] Failed to cleanup {old_file}: {e}")
                    
        except Exception as e:
            print(f"[BrowserTool] Screenshot cleanup error: {e}")
    
    async def _close_session(self, session_id: str):
        """
        Close browser session and cleanup resources.
        
        Args:
            session_id: Session identifier to close
        """
        if session_id not in self._sessions:
            print(f"[BrowserTool] Session not found: {session_id}")
            return
        
        session = self._sessions[session_id]
        
        try:
            # Close in reverse order: page -> context -> browser -> playwright
            if "page" in session:
                try:
                    await session["page"].close()
                except:
                    pass
                    
            if "context" in session:
                try:
                    await session["context"].close()
                except:
                    pass
                    
            if "browser" in session:
                try:
                    await session["browser"].close()
                except:
                    pass
                    
            if "playwright" in session:
                try:
                    await session["playwright"].stop()
                except:
                    pass
            
            # Remove from sessions dict
            del self._sessions[session_id]
            
            # Cleanup all screenshots for this session
            self._cleanup_session_screenshots(session_id)
            
            print(f"[BrowserTool] Session {session_id} fully closed")
            
        except Exception as e:
            print(f"[BrowserTool] Error closing session {session_id}: {e}")
    
    def _cleanup_session_screenshots(self, session_id: str):
        """
        Remove all screenshots for a closed session.
        
        Args:
            session_id: Session whose screenshots should be deleted
        """
        pattern = f"browser_{session_id}_*.png"
        temp_dir = tempfile.gettempdir()
        
        try:
            count = 0
            for f in os.listdir(temp_dir):
                if fnmatch.fnmatch(f, pattern):
                    try:
                        os.remove(os.path.join(temp_dir, f))
                        count += 1
                    except:
                        pass
            
            if count > 0:
                print(f"[BrowserTool] Cleaned up {count} screenshots for session {session_id}")
                
        except Exception as e:
            print(f"[BrowserTool] Error cleaning up session screenshots: {e}")
    
    def get_active_sessions(self) -> List[str]:
        """Return list of active session IDs."""
        return list(self._sessions.keys())
    
    async def close_all_sessions(self):
        """Close all active browser sessions."""
        session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            await self._close_session(session_id)
    
    def verify(self, action: Action, result: ToolResult) -> dict:
        """
        Browser-specific verification helper.
        
        Returns verification data including screenshot count and session status.
        """
        artifacts = result.artifacts
        screenshots = artifacts.get("screenshots", [])
        extracted = artifacts.get("extracted_data", {})
        session_id = artifacts.get("session_id")
        
        # Check if session is still active
        session_active = session_id in self._sessions
        
        return {
            "tool_verified": result.success,
            "screenshot_count": len(screenshots),
            "extracted_data_count": len(extracted),
            "operations_completed": artifacts.get("operations_completed", 0),
            "last_screenshot": screenshots[-1] if screenshots else None,
            "session_active": session_active,
            "session_id": session_id,
            "final_url": artifacts.get("url")
        }
    
    def apply_failure_fix(self, action: Action, hint: str) -> Optional[Action]:
        """
        Apply browser-specific failure fixes.
        
        Args:
            action: The failed Action
            hint: The failure hint
            
        Returns:
            Modified Action or None if no fix can be applied
        """
        # Browser-specific retry logic
        if hint == "timeout":
            # Increase timeout for wait operations
            new_payload = action.payload.copy()
            operations = new_payload.get("operations", [])
            for op in operations:
                if op.get("type") in ["wait", "wait_for_load"]:
                    op["timeout"] = op.get("timeout", 5000) * 2
            
            return Action(
                type=action.type,
                payload=new_payload,
                description=f"{action.description} (retry with longer timeout)",
                timeout=action.timeout * 2
            )
            
        elif hint == "missing_element":
            # Try with more generic selector
            new_payload = action.payload.copy()
            operations = new_payload.get("operations", [])
            for op in operations:
                if "selector" in op:
                    # Try text-based selector as fallback
                    selector = op["selector"]
                    if selector.startswith("#"):
                        # Convert ID to partial match
                        op["selector"] = f"[id*='{selector[1:]}']"
            
            return Action(
                type=action.type,
                payload=new_payload,
                description=f"{action.description} (retry with fallback selectors)",
                timeout=action.timeout
            )
        
        return None
    
    def classify_failure(self, result: ToolResult) -> str:
        """
        Classify browser failures from ToolResult.
        
        Args:
            result: The failed ToolResult
            
        Returns:
            Failure hint string
        """
        if result.success:
            return "none"
        
        error = result.error or ""
        error_lower = error.lower()
        
        # Playwright-specific error classification
        if "timeout" in error_lower:
            return "timeout"
        elif "selector" in error_lower and ("not found" in error_lower or "resolved" in error_lower):
            return "missing_element"
        elif "navigation" in error_lower or "net::" in error_lower:
            return "navigation_failed"
        elif "permission" in error_lower or "denied" in error_lower:
            return "permission_denied"
        elif "browser" in error_lower and ("not installed" in error_lower or "executable" in error_lower):
            return "missing_dependency"
        
        return "unknown"
    
    def get_schema(self) -> dict:
        """
        Return schema for web_crawl action.
        """
        return {
            "type": "web_crawl",
            "description": "Web automation using Playwright with DOM-based interaction (not OCR)",
            "payload_schema": {
                "session_id": "Optional existing session to reuse",
                "url": "Starting URL",
                "operations": "List of operations to perform",
                "headless": "Whether to run in headless mode (default: False)",
                "slow_mo": "Delay between actions in ms (default: 500)",
                "browser_type": "chromium, firefox, or webkit (default: chromium)"
            },
            "selector_strategies": [
                "data-testid attributes: [data-testid='submit-button']",
                "ID selectors: #submit-button, #search-input",
                "ARIA labels: [aria-label='Search'], [aria-label='Submit']",
                "Name attributes: [name='search'], [name='email']",
                "Placeholder: [placeholder='Enter email']",
                "Text content: button:has-text('Submit'), a:has-text('Next')",
                "Class + structure: .product-list > .product-item:first-child"
            ],
            "operation_types": [
                "goto: Navigate to URL",
                "click: Click element by selector",
                "fill: Fill input field (clears existing)",
                "type: Type text with keystroke delay (human-like)",
                "select: Select dropdown option (by value, label, or index)",
                "wait: Wait for element to appear/become visible",
                "wait_for_load: Wait for page load state (networkidle, load, domcontentloaded)",
                "extract: Extract text or attributes from elements",
                "scroll: Scroll page (direction: up, down, top, bottom) or scroll element into view",
                "hover: Hover over element (triggers hover states)",
                "press: Press keyboard key (Enter, Tab, Escape, etc.)",
                "evaluate: Execute JavaScript and return result",
                "screenshot: Capture screenshot at this point",
                "close: Close browser session (always include as final operation)"
            ],
            "failure_hints": [
                "timeout: Page load or element wait timed out (try longer timeout or different selector)",
                "missing_element: Element not found with given selector (try different selector strategy)",
                "navigation_failed: Could not navigate to URL (check URL, network, or site availability)",
                "permission_denied: Browser blocked by permissions or security settings",
                "missing_dependency: Playwright or browser not installed",
                "none: No specific classification or not a failure"
            ]
        }
    
    def get_examples(self) -> list[dict]:
        """
        Return example web_crawl actions.
        """
        return [
            {
                "payload": {
                    "url": "https://google.com",
                    "operations": [
                        {"type": "fill", "selector": "[name='q']", "value": "python tutorial"},
                        {"type": "press", "key": "Enter"},
                        {"type": "wait", "selector": "#search", "timeout": 5000},
                        {"type": "extract", "selector": "h3", "as": "results", "limit": 5},
                        {"type": "close"}
                    ],
                    "headless": False,
                    "slow_mo": 300
                },
                "description": "Search for Python tutorials on Google",
                "timeout": 60
            },
            {
                "payload": {
                    "url": "https://amazon.com/s?k=laptop",
                    "operations": [
                        {"type": "wait", "selector": "[data-component-type='s-search-result']"},
                        {"type": "extract", "selector": "[data-component-type='s-search-result'] h2 a span", "as": "titles", "limit": 10},
                        {"type": "extract", "selector": ".a-price-whole", "as": "prices", "limit": 10},
                        {"type": "close"}
                    ],
                    "headless": False
                },
                "description": "Extract laptop prices from Amazon search results",
                "timeout": 60
            },
            {
                "payload": {
                    "session_id": "my_session_123",
                    "url": "https://example.com/login",
                    "operations": [
                        {"type": "fill", "selector": "#username", "value": "user@example.com"},
                        {"type": "fill", "selector": "#password", "value": "password123"},
                        {"type": "click", "selector": "#login-button"},
                        {"type": "wait", "selector": ".dashboard", "timeout": 10000},
                        {"type": "goto", "url": "https://example.com/dashboard/reports"},
                        {"type": "wait", "selector": ".report-table"},
                        {"type": "extract", "selector": ".report-row", "as": "reports", "limit": 20},
                        {"type": "close"}
                    ]
                },
                "description": "Login and extract reports from dashboard",
                "timeout": 120
            },
            {
                "payload": {
                    "url": "https://example.com",
                    "operations": [
                        {"type": "goto", "url": "https://example.com/products"},
                        {"type": "wait", "selector": ".product-item"},
                        {"type": "click", "selector": ".product-item:first-child"},
                        {"type": "wait", "selector": ".product-details"},
                        {"type": "extract", "selector": ".product-title", "as": "title"},
                        {"type": "extract", "selector": ".product-price", "as": "price"},
                        {"type": "close"}
                    ],
                    "headless": False,
                    "slow_mo": 500
                },
                "description": "Navigate to products and extract first item details",
                "timeout": 60
            }
        ]


# Make BrowserTool available for import
__all__ = ["BrowserTool"]
