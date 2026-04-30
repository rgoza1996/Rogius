"""
Rogius TUI - Terminal User Interface

A standalone Python TUI using Textual for AI chat with terminal integration.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Input,
    Static,
    Header,
    Footer,
    Button,
    Label,
    ListView,
    ListItem,
    TabbedContent,
    TabPane,
    ProgressBar,
    Checkbox
)
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.message import Message

from launcher import OSDetector
from shell_runner import ShellRunner, CommandResult
from multistep import (
    PlanManager, MultiStepPlan, Step, StepStatus, PlanStatus,
    get_plan_progress, modify_step, skip_step
)
from ai_client import AIClient, ConversationManager
from settings import (
    load_settings, save_settings, TUISettings,
    get_api_config_from_settings
)


class SettingsScreen(ModalScreen):
    """Settings modal screen with persistence."""
    
    def __init__(self, settings: TUISettings, **kwargs):
        super().__init__(**kwargs)
        self.settings = settings
    
    def compose(self) -> ComposeResult:
        yield Static("Settings", classes="settings-title")
        
        with TabbedContent(classes="settings-container"):
            with TabPane("Chat API", id="tab-chat"):
                with Vertical(classes="settings-section"):
                    yield Label("API Endpoint:")
                    yield Input(
                        value=self.settings.chat_endpoint,
                        placeholder="http://localhost:1234/v1/chat/completions",
                        id="chat-endpoint"
                    )
                    
                    yield Label("API Key (optional):")
                    yield Input(
                        value=self.settings.chat_api_key,
                        placeholder="sk-...",
                        id="chat-api-key",
                        password=True
                    )
                    
                    yield Label("Model:")
                    yield Input(
                        value=self.settings.chat_model,
                        placeholder="llama-3.1-8b",
                        id="chat-model"
                    )
                    
                    yield Label("Max Response Tokens:")
                    yield Input(
                        value=str(self.settings.chat_context_length),
                        placeholder="4096",
                        id="chat-context-length"
                    )
            
            with TabPane("TTS", id="tab-tts"):
                with Vertical(classes="settings-section"):
                    yield Label("TTS Endpoint:")
                    yield Input(
                        value=self.settings.tts_endpoint,
                        placeholder="http://100.71.89.62:8880/v1/audio/speech",
                        id="tts-endpoint"
                    )
                    
                    yield Label("Voice:")
                    yield Input(
                        value=self.settings.tts_voice,
                        placeholder="af_bella",
                        id="tts-voice"
                    )
                    
                    yield Label("Auto-play audio:")
                    yield Checkbox(
                        value=self.settings.auto_play_audio,
                        id="auto-play-audio"
                    )
            
            with TabPane("Behavior", id="tab-behavior"):
                with Vertical(classes="settings-section"):
                    yield Label("Auto-execute multi-step:")
                    yield Checkbox(
                        value=self.settings.auto_execute_multistep,
                        id="auto-execute-multistep"
                    )
                    
                    yield Label("Confirm destructive commands:")
                    yield Checkbox(
                        value=self.settings.confirm_destructive,
                        id="confirm-destructive"
                    )
        
        with Horizontal(classes="settings-buttons"):
            yield Button("Save", id="save-settings", variant="primary")
            yield Button("Cancel", id="cancel-settings")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-settings":
            # Gather values from inputs
            self.settings.chat_endpoint = self.query_one("#chat-endpoint", Input).value
            self.settings.chat_api_key = self.query_one("#chat-api-key", Input).value
            self.settings.chat_model = self.query_one("#chat-model", Input).value
            
            try:
                self.settings.chat_context_length = int(self.query_one("#chat-context-length", Input).value)
            except ValueError:
                pass
            
            self.settings.tts_endpoint = self.query_one("#tts-endpoint", Input).value
            self.settings.tts_voice = self.query_one("#tts-voice", Input).value
            
            self.settings.auto_play_audio = self.query_one("#auto-play-audio", Checkbox).value
            self.settings.auto_execute_multistep = self.query_one("#auto-execute-multistep", Checkbox).value
            self.settings.confirm_destructive = self.query_one("#confirm-destructive", Checkbox).value
            
            save_settings(self.settings)
            self.dismiss(self.settings)
        else:
            self.dismiss(None)


class MessageWidget(Static):
    """Widget for displaying a chat message."""
    
    def __init__(self, role: str, content: str, **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.content = content
        self.add_class(f"message-{role}")
    
    def compose(self) -> ComposeResult:
        role_label = "You" if self.role == "user" else "AI"
        yield Static(f"**{role_label}:**", classes="message-role")
        yield Static(self.content, classes="message-content")


class CommandOutputWidget(Static):
    """Widget for displaying command output."""
    
    def __init__(self, result: CommandResult, **kwargs):
        super().__init__(**kwargs)
        self.result = result
        self.add_class("command-output")
    
    def compose(self) -> ComposeResult:
        status_color = "success" if self.result.exit_code == 0 else "error"
        yield Static(f"$ {self.result.command}", classes="command-cmd")
        yield Static(f"Exit: {self.result.exit_code} ({status_color})", classes=f"command-status {status_color}")
        
        if self.result.stdout:
            with Vertical(classes="command-section"):
                yield Static("STDOUT:", classes="section-label")
                yield Static(self.result.stdout, classes="command-stdout")
        
        if self.result.stderr:
            with Vertical(classes="command-section"):
                yield Static("STDERR:", classes="section-label")
                yield Static(self.result.stderr, classes="command-stderr")


class SystemInfoWidget(Static):
    """Widget displaying system information."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.system_info = OSDetector.get_system_info()
    
    def compose(self) -> ComposeResult:
        yield Static("System Information", classes="panel-title")
        
        with Vertical(classes="info-grid"):
            yield Label(f"OS: {self.system_info['os']} {self.system_info['os_version']}")
            yield Label(f"Architecture: {self.system_info['architecture']}")
            yield Label(f"Shell: {self.system_info['shell']}")
            yield Label(f"Hostname: {self.system_info['hostname']}")
            yield Label(f"User: {self.system_info['username']}")
            yield Label(f"Python: {self.system_info['python_version']}")


class CommandHistoryWidget(Static):
    """Widget displaying command history."""
    
    def __init__(self, runner: ShellRunner, **kwargs):
        super().__init__(**kwargs)
        self.runner = runner
    
    def compose(self) -> ComposeResult:
        yield Static("Command History", classes="panel-title")
        self.list_view = ListView(classes="command-list")
        yield self.list_view
        yield Button("Clear History", id="clear-history", variant="error")
    
    def update_history(self):
        """Update the command history list."""
        self.list_view.clear()
        for result in reversed(self.runner.get_history()):
            status = "✓" if result.exit_code == 0 else "✗"
            item_text = f"{status} {result.command[:50]}..." if len(result.command) > 50 else f"{status} {result.command}"
            self.list_view.append(ListItem(Static(item_text)))
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "clear-history":
            self.runner.clear_history()
            self.update_history()


class StepWidget(Static):
    """Widget displaying a single step in a plan."""
    
    def __init__(self, step: Step, index: int, **kwargs):
        super().__init__(**kwargs)
        self.step = step
        self.index = index
        self.update_classes()
    
    def update_classes(self):
        """Update CSS classes based on step status."""
        self.remove_class("step-pending", "step-running", "step-completed", "step-error", "step-skipped")
        self.add_class(f"step-{self.step.status.value}")
    
    def compose(self) -> ComposeResult:
        with Horizontal(classes="step-container"):
            # Status icon
            status_icon = {
                StepStatus.PENDING: "○",
                StepStatus.RUNNING: "◐",
                StepStatus.COMPLETED: "✓",
                StepStatus.ERROR: "✗",
                StepStatus.SKIPPED: "⊘"
            }.get(self.step.status, "○")
            
            yield Static(status_icon, classes=f"step-icon step-icon-{self.step.status.value}")
            
            with Vertical(classes="step-content"):
                yield Static(f"Step {self.index + 1}: {self.step.description}", classes="step-description")
                yield Static(f"$ {self.step.command}", classes="step-command")
                
                if self.step.result:
                    yield Static(self.step.result[:200], classes="step-result")
                if self.step.error:
                    yield Static(self.step.error[:200], classes="step-error-text")
    
    def refresh_step(self):
        """Refresh the step display."""
        self.update_classes()
        self.refresh()


class PlanWidget(Static):
    """Widget displaying an active multi-step plan."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.plan: Optional[MultiStepPlan] = None
        self.step_widgets: list[StepWidget] = []
    
    def compose(self) -> ComposeResult:
        yield Static("No active plan", id="plan-title", classes="panel-title")
        
        with Vertical(id="plan-progress-container"):
            yield ProgressBar(id="plan-progress", show_eta=False)
        
        with VerticalScroll(id="plan-steps", classes="plan-steps-container"):
            yield Static("Create a plan with /plan <goal>", classes="plan-empty")
        
        with Horizontal(classes="plan-controls"):
            yield Button("Next Step", id="plan-next", variant="primary", disabled=True)
            yield Button("Skip", id="plan-skip", disabled=True)
            yield Button("Clear", id="plan-clear", variant="error", disabled=True)
    
    def set_plan(self, plan: Optional[MultiStepPlan]):
        """Set the active plan and update display."""
        self.plan = plan
        self.step_widgets = []
        
        if not plan:
            self.query_one("#plan-title", Static).update("No active plan")
            self.query_one("#plan-progress", ProgressBar).update(progress=0, total=100)
            
            steps_container = self.query_one("#plan-steps", VerticalScroll)
            steps_container.remove_children()
            steps_container.mount(Static("Create a plan with /plan <goal>", classes="plan-empty"))
            
            self._disable_controls()
            return
        
        # Update title
        progress = get_plan_progress(plan)
        self.query_one("#plan-title", Static).update(
            f"📋 {plan.goal[:40]}{'...' if len(plan.goal) > 40 else ''} "
            f"({progress['completed']}/{progress['total']})"
        )
        
        # Update progress bar
        self.query_one("#plan-progress", ProgressBar).update(
            progress=progress['percentage'],
            total=100
        )
        
        # Update steps
        steps_container = self.query_one("#plan-steps", VerticalScroll)
        steps_container.remove_children()
        
        for i, step in enumerate(plan.steps):
            step_widget = StepWidget(step, i)
            self.step_widgets.append(step_widget)
            steps_container.mount(step_widget)
        
        # Enable controls
        self._update_controls()
    
    def update_progress(self):
        """Update the progress display."""
        if not self.plan:
            return
        
        progress = get_plan_progress(self.plan)
        
        # Update title
        self.query_one("#plan-title", Static).update(
            f"📋 {self.plan.goal[:40]}{'...' if len(self.plan.goal) > 40 else ''} "
            f"({progress['completed']}/{progress['total']})"
        )
        
        # Update progress bar
        self.query_one("#plan-progress", ProgressBar).update(
            progress=progress['percentage'],
            total=100
        )
        
        # Refresh step widgets
        for widget in self.step_widgets:
            widget.refresh_step()
        
        self._update_controls()
    
    def _update_controls(self):
        """Update control button states."""
        if not self.plan:
            self._disable_controls()
            return
        
        is_running = self.plan.status == PlanStatus.RUNNING
        has_more_steps = self.plan.current_step_index < len(self.plan.steps)
        
        self.query_one("#plan-next", Button).disabled = not (is_running and has_more_steps)
        self.query_one("#plan-skip", Button).disabled = not (is_running and has_more_steps)
        self.query_one("#plan-clear", Button).disabled = False
    
    def _disable_controls(self):
        """Disable all control buttons."""
        self.query_one("#plan-next", Button).disabled = True
        self.query_one("#plan-skip", Button).disabled = True
        self.query_one("#plan-clear", Button).disabled = True
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle control button presses."""
        if event.button.id == "plan-clear":
            self.set_plan(None)
            # Notify parent to clear plan in plan manager
            self.post_message(self.PlanClear())
    
    class PlanClear(Message):
        """Message sent when plan should be cleared."""
        pass


class RogiusTUI(App):
    """Main TUI application for Rogius."""
    
    CSS = """
    Screen {
        align: center middle;
    }
    
    #main-container {
        width: 100%;
        height: 100%;
    }
    
    #sidebar {
        width: 25%;
        height: 100%;
        border: solid $primary;
        padding: 1;
    }
    
    #chat-container {
        width: 75%;
        height: 100%;
        border: solid $primary;
    }
    
    #messages-scroll {
        height: 60%;
        border-bottom: solid $primary;
        padding: 1;
    }
    
    #terminal-output {
        height: 40%;
        padding: 1;
    }
    
    #input-area {
        height: auto;
        border-top: solid $primary;
        padding: 1;
    }
    
    #message-input {
        width: 85%;
    }
    
    #send-button {
        width: 15%;
    }
    
    .message-user {
        background: $surface;
        color: $text;
        padding: 1;
        margin: 1 0;
        border-left: solid $primary;
    }
    
    .message-assistant {
        background: $surface-darken-1;
        color: $text;
        padding: 1;
        margin: 1 0;
        border-left: solid $success;
    }
    
    .message-role {
        text-style: bold;
        color: $primary;
    }
    
    .message-content {
        margin-top: 1;
    }
    
    .panel-title {
        text-style: bold;
        color: $primary;
        text-align: center;
        padding: 1 0;
    }
    
    .command-output {
        background: $surface-darken-1;
        padding: 1;
        margin: 1 0;
    }
    
    .command-cmd {
        color: $primary;
        text-style: bold;
    }
    
    .command-status {
        margin: 1 0;
    }
    
    .success {
        color: $success;
    }
    
    .error {
        color: $error;
    }
    
    .text-muted {
        color: $text 50%;
    }
    
    .section-label {
        text-style: bold;
        color: $text 50%;
        margin-top: 1;
    }
    
    .command-stdout {
        color: $text;
    }
    
    .command-stderr {
        color: $error;
    }
    
    .info-grid {
        padding: 1;
    }
    
    .info-grid Label {
        padding: 1 0;
    }
    
    .settings-title {
        text-align: center;
        text-style: bold;
        padding: 1;
    }
    
    .settings-container {
        padding: 2;
        width: 80%;
    }
    
    .system-prompt-area {
        height: 10;
    }
    
    .settings-buttons {
        margin-top: 2;
        align: center middle;
        height: auto;
    }
    
    .settings-section {
        padding: 1;
    }
    
    .settings-section Label {
        margin-top: 1;
    }
    
    /* Plan Widget Styles */
    #plan-widget {
        height: 50%;
        border-top: solid $primary;
        padding: 1;
    }
    
    #plan-progress-container {
        padding: 1 0;
    }
    
    .plan-steps-container {
        height: 1fr;
        overflow-y: auto;
    }
    
    .plan-empty {
        text-align: center;
        color: $text 50%;
        padding: 2;
    }
    
    .plan-controls {
        height: auto;
        padding: 1 0;
        align: center middle;
    }
    
    /* Step Widget Styles */
    .step-container {
        padding: 1;
        margin: 0 0 1 0;
        border: solid $surface;
    }
    
    .step-pending {
        border: solid $surface-lighten-1;
    }
    
    .step-running {
        border: solid $primary;
        background: $surface-darken-1;
    }
    
    .step-completed {
        border: solid $success;
        background: $success-darken-3;
    }
    
    .step-error {
        border: solid $error;
        background: $error-darken-3;
    }
    
    .step-skipped {
        border: solid $surface-lighten-1;
        opacity: 0.7;
    }
    
    .step-icon {
        width: 3;
        text-align: center;
        text-style: bold;
    }
    
    .step-icon-pending {
        color: $text 50%;
    }
    
    .step-icon-running {
        color: $primary;
    }
    
    .step-icon-completed {
        color: $success;
    }
    
    .step-icon-error {
        color: $error;
    }
    
    .step-icon-skipped {
        color: $text 50%;
    }
    
    .step-content {
        padding: 0 1;
    }
    
    .step-description {
        text-style: bold;
    }
    
    .step-command {
        color: $text 50%;
        text-style: italic;
        margin: 0 0 1 0;
    }
    
    .step-result {
        color: $text;
        text-style: dim;
        margin: 0 0 1 0;
    }
    
    .step-error-text {
        color: $error;
        margin: 0 0 1 0;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+s", "settings", "Settings", show=True),
        Binding("ctrl+c", "cancel", "Cancel", show=True),
        Binding("ctrl+p", "toggle_plan", "Plan", show=True),
        Binding("ctrl+n", "next_step", "Next Step", show=True),
        Binding("escape", "cancel", show=False),
    ]
    
    def __init__(self):
        super().__init__()
        self.shell_runner = ShellRunner()
        self.messages: list[dict] = []
        
        # Load settings
        self.settings = load_settings()
        
        # Initialize AI client
        api_config = get_api_config_from_settings(self.settings)
        self.ai_client = AIClient(api_config)
        self.conversation = ConversationManager(api_config.system_prompt)
        
        # Initialize plan manager
        self.plan_manager = PlanManager()
        self._cancel_event: Optional[asyncio.Event] = None
        
        # State
        self.is_streaming = False
        self.is_executing_plan = False
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Horizontal(id="main-container"):
            # Sidebar with system info, command history, and plan widget
            with Vertical(id="sidebar"):
                yield SystemInfoWidget()
                yield CommandHistoryWidget(self.shell_runner)
                yield PlanWidget(id="plan-widget")
            
            # Main chat area
            with Vertical(id="chat-container"):
                # Messages area
                with VerticalScroll(id="messages-scroll"):
                    yield Static(
                        "Welcome to Rogius TUI!\n\n"
                        "Commands:\n"
                        "  $ <cmd> - Execute terminal command\n"
                        "  /plan <goal> - Create multi-step plan\n"
                        "  /step - Execute next step\n"
                        "  /modify <n> <cmd> - Modify step\n"
                        "  /skip [n] - Skip step\n"
                        "  /verify - Verify plan completion\n"
                        "  /clear - Clear chat\n"
                        "  /help - Show all commands\n\n"
                        "Shortcuts: Ctrl+S Settings, Ctrl+P Plan, Ctrl+N Next Step, Ctrl+Q Quit",
                        id="welcome-message",
                        classes="message-assistant"
                    )
                
                # Terminal output area
                with VerticalScroll(id="terminal-output"):
                    yield Static("Terminal output will appear here...", classes="text-muted")
                
                # Input area
                with Horizontal(id="input-area"):
                    yield Input(placeholder="Type your message or command...", id="message-input")
                    yield Button("Send", id="send-button", variant="primary")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self.query_one("#message-input", Input).focus()
    
    def action_settings(self) -> None:
        """Open settings screen."""
        def on_settings_saved(new_settings):
            if new_settings:
                self.settings = new_settings
                # Re-initialize AI client with new config
                api_config = get_api_config_from_settings(self.settings)
                self.ai_client = AIClient(api_config)
                self.conversation = ConversationManager(api_config.system_prompt)
                self.add_message("assistant", "Settings saved and applied.")
        
        self.push_screen(SettingsScreen(self.settings), on_settings_saved)
    
    def action_toggle_plan(self) -> None:
        """Toggle plan widget visibility (scroll to it)."""
        plan_widget = self.query_one("#plan-widget", PlanWidget)
        plan_widget.scroll_visible()
    
    def action_next_step(self) -> None:
        """Execute the next step in the active plan."""
        if self.plan_manager.active_plan:
            asyncio.create_task(self._execute_next_step())
        else:
            self.add_message("assistant", "No active plan. Create one with /plan <goal>")
    
    def action_cancel(self) -> None:
        """Cancel current operation."""
        if self.is_streaming:
            self._cancel_event = asyncio.Event()
            self._cancel_event.set()
            self.is_streaming = False
            self.add_message("assistant", "Response cancelled.")
        elif self.is_executing_plan:
            self.plan_manager.cancel()
            self.is_executing_plan = False
            self.add_message("assistant", "Plan execution cancelled.")
    
    def add_message(self, role: str, content: str):
        """Add a message to the chat."""
        self.messages.append({"role": role, "content": content})
        messages_container = self.query_one("#messages-scroll", VerticalScroll)
        message_widget = MessageWidget(role, content)
        messages_container.mount(message_widget)
        messages_container.scroll_end(animate=False)
    
    def add_command_output(self, result: CommandResult):
        """Add command output to terminal panel."""
        terminal_container = self.query_one("#terminal-output", VerticalScroll)
        # Clear placeholder if first command
        if len(terminal_container.children) == 1 and isinstance(terminal_container.children[0], Static):
            if "will appear here" in str(terminal_container.children[0].render()):
                terminal_container.remove_children()
        
        output_widget = CommandOutputWidget(result)
        terminal_container.mount(output_widget)
        terminal_container.scroll_end(animate=False)
        
        # Update command history
        history_widget = self.query_one(CommandHistoryWidget)
        history_widget.update_history()
    
    async def send_message(self, content: str, enable_tools: bool = True):
        """Send a message to the AI with streaming and tool support."""
        self.add_message("user", content)
        self.conversation.add_user_message(content)
        
        self.is_streaming = True
        self._cancel_event = asyncio.Event()
        
        # Create placeholder for assistant response
        assistant_content = ""
        pending_tool_calls = []
        
        try:
            messages = self.conversation.get_messages()
            
            async for chunk in self.ai_client.stream_chat_completion(
                messages,
                enable_tools=enable_tools,
                signal=self._cancel_event
            ):
                if self._cancel_event and self._cancel_event.is_set():
                    break
                
                if chunk.content:
                    # Skip object-like content (tool call remnants)
                    if "[object Object]" not in str(chunk.content):
                        assistant_content += str(chunk.content)
                        # Update the last assistant message or create new
                        if self.messages and self.messages[-1].get("role") == "assistant":
                            self.messages[-1]["content"] = assistant_content
                        else:
                            self.add_message("assistant", assistant_content)
                
                if chunk.tool_calls:
                    pending_tool_calls.extend(chunk.tool_calls)
            
            # Handle tool calls
            if pending_tool_calls and not (self._cancel_event and self._cancel_event.is_set()):
                tool_results = await self._execute_tool_calls(pending_tool_calls)
                
                # Add tool results to conversation and continue
                for tool_name, result in tool_results:
                    assistant_content += f"\n\n[{tool_name}]: {result}"
                    self.conversation.add_tool_result(tool_name, result)
                
                # Update final message
                if self.messages and self.messages[-1].get("role") == "assistant":
                    self.messages[-1]["content"] = assistant_content
                    # Refresh display
                    self._refresh_last_message()
            
            # Save to conversation history
            if assistant_content:
                self.conversation.add_assistant_message(assistant_content)
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.add_message("assistant", error_msg)
        finally:
            self.is_streaming = False
    
    def _refresh_last_message(self):
        """Refresh the last message in the display."""
        messages_container = self.query_one("#messages-scroll", VerticalScroll)
        # Remove and re-add the last message
        if self.messages:
            children = list(messages_container.children)
            if children:
                children[-1].remove()
                last_msg = self.messages[-1]
                message_widget = MessageWidget(last_msg["role"], last_msg["content"])
                messages_container.mount(message_widget)
                messages_container.scroll_end(animate=False)
    
    async def _execute_tool_calls(self, tool_calls) -> list[tuple[str, str]]:
        """Execute tool calls and return results."""
        results = []
        
        for tc in tool_calls:
            tool_name = tc.function_name
            if not tool_name:
                continue
            
            try:
                args = json.loads(tc.function_arguments) if tc.function_arguments else {}
            except json.JSONDecodeError:
                args = {}
            
            result = await self._execute_tool(tool_name, args)
            results.append((tool_name, result))
        
        return results
    
    async def _execute_tool(self, tool_name: str, args: dict) -> str:
        """Execute a single tool."""
        if tool_name == "execute_command":
            command = args.get("command", "")
            if not command:
                return "Error: No command provided"
            
            result = self.shell_runner.run(command)
            output = result.stdout or result.stderr or "(no output)"
            return f"Exit {result.exit_code}: {output[:500]}"
        
        elif tool_name == "start_multistep_task":
            goal = args.get("goal", "Task")
            steps = args.get("steps", [])
            
            plan = self.plan_manager.create_plan(goal, steps)
            self._update_plan_widget()
            
            if self.settings.auto_execute_multistep:
                asyncio.create_task(self._auto_execute_plan())
                return f"Plan created with {len(steps)} steps. Auto-executing..."
            else:
                return f"Plan created with {len(steps)} steps. Use /step to execute."
        
        elif tool_name == "execute_next_step":
            if not self.plan_manager.active_plan:
                return "No active plan"
            
            await self._execute_next_step()
            plan = self.plan_manager.active_plan
            if plan:
                progress = get_plan_progress(plan)
                return f"Step {plan.current_step_index}/{len(plan.steps)} - {progress['percentage']}% complete"
            return "Plan completed"
        
        elif tool_name == "modify_step":
            new_command = args.get("newCommand", "")
            new_description = args.get("newDescription")
            
            if self.plan_manager.modify_current_step(new_command, new_description):
                self._update_plan_widget()
                return f"Step modified to: {new_command}"
            return "Failed to modify step"
        
        elif tool_name == "skip_step":
            if self.plan_manager.skip_current_step():
                self._update_plan_widget()
                return "Step skipped"
            return "Failed to skip step"
        
        elif tool_name == "add_step":
            description = args.get("description", "")
            command = args.get("command", "")
            
            if self.plan_manager.add_step_after_current(description, command):
                self._update_plan_widget()
                return f"Step added: {description}"
            return "Failed to add step"
        
        elif tool_name == "verify_task_completion":
            result = self.plan_manager.verify_completion()
            return json.dumps(result, indent=2)
        
        elif tool_name == "open_terminal":
            # Terminal is always visible in TUI
            return "Terminal panel ready"
        
        else:
            return f"Unknown tool: {tool_name}"
    
    def _update_plan_widget(self):
        """Update the plan widget display."""
        plan_widget = self.query_one("#plan-widget", PlanWidget)
        plan_widget.set_plan(self.plan_manager.active_plan)
    
    async def _execute_next_step(self):
        """Execute the next step in the active plan."""
        if not self.plan_manager.active_plan:
            self.add_message("assistant", "No active plan")
            return
        
        self.is_executing_plan = True
        
        async def step_executor(cmd: str) -> tuple[str, str, int]:
            result = self.shell_runner.run(cmd)
            return (result.stdout, result.stderr, result.exit_code)
        
        async def on_step_start(step, idx):
            self._update_plan_widget()
            self.add_message("assistant", f"▶ Step {idx + 1}: {step.description}")
        
        async def on_step_complete(step, idx, result):
            self._update_plan_widget()
            self.add_command_output(self.shell_runner.get_history()[-1] if self.shell_runner.get_history() else None)
        
        async def on_step_error(step, idx, error):
            self._update_plan_widget()
            self.add_message("assistant", f"❌ Step {idx + 1} failed: {error}")
        
        task = self.plan_manager.execute_next_step(step_executor)
        if task:
            # Wait for the task to complete
            while not task.done():
                await asyncio.sleep(0.1)
                self._update_plan_widget()
            
            await task
            self._update_plan_widget()
        
        self.is_executing_plan = False
        
        # Auto-continue if enabled and plan still running
        plan = self.plan_manager.active_plan
        if (plan and plan.status == PlanStatus.RUNNING and 
            self.settings.auto_execute_multistep and
            plan.current_step_index < len(plan.steps)):
            # Check if last step succeeded
            if plan.steps[plan.current_step_index - 1].status == StepStatus.COMPLETED:
                await asyncio.sleep(0.5)
                await self._execute_next_step()
    
    async def _auto_execute_plan(self):
        """Auto-execute all steps in the plan."""
        if not self.plan_manager.active_plan:
            return
        
        self.is_executing_plan = True
        
        async def step_executor(cmd: str) -> tuple[str, str, int]:
            result = self.shell_runner.run(cmd)
            return (result.stdout, result.stderr, result.exit_code)
        
        async def on_step_start(step, idx):
            self._update_plan_widget()
        
        async def on_step_complete(step, idx, result):
            self._update_plan_widget()
        
        async def on_step_error(step, idx, error):
            self._update_plan_widget()
            self.add_message("assistant", f"❌ Step {idx + 1} failed: {error}")
        
        result = await self.plan_manager.execute(
            step_executor,
            on_step_start,
            on_step_complete,
            on_step_error
        )
        
        self._update_plan_widget()
        self.is_executing_plan = False
        
        # Summary message
        progress = get_plan_progress(result)
        self.add_message(
            "assistant",
            f"📋 Plan complete: {progress['completed']}/{progress['total']} steps "
            f"({progress['percentage']}%) - Status: {result.status.value}"
        )
    
    def execute_terminal_command(self, command: str):
        """Execute a terminal command."""
        result = self.shell_runner.run(command)
        self.add_command_output(result)
        return result
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "send-button":
            self.handle_input()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.input.id == "message-input":
            self.handle_input()
    
    def handle_input(self):
        """Process user input."""
        input_widget = self.query_one("#message-input", Input)
        content = input_widget.value.strip()
        
        if not content:
            return
        
        input_widget.value = ""
        
        # Check if it's a terminal command (starts with $ or /)
        if content.startswith("$"):
            # Execute as terminal command
            command = content[1:].strip()
            self.add_message("user", f"Terminal: {command}")
            self.execute_terminal_command(command)
        elif content.startswith("/"):
            # Handle slash commands
            self.handle_slash_command(content)
        else:
            # Send as chat message
            asyncio.create_task(self.send_message(content))
    
    def handle_slash_command(self, command: str):
        """Handle slash commands."""
        parts = command.split(maxsplit=2)
        cmd = parts[0].lower()
        
        if cmd == "/help":
            help_text = """
Available commands:
  /help - Show this help message
  /clear - Clear chat history
  /cd <path> - Change working directory
  /pwd - Show current directory
  /ls [path] - List directory contents
  /settings - Open settings
  
Multi-Step Commands:
  /plan <goal> [steps_json] - Create a plan (or AI will generate steps)
  /step - Execute next step in active plan
  /modify <step_num> <new_command> - Modify a step
  /skip [step_num] - Skip current or specified step
  /add <description> | <command> - Add step after current
  /verify - Verify plan completion
  /clearplan - Clear active plan
            """
            self.add_message("assistant", help_text)
        
        elif cmd == "/clear":
            messages_container = self.query_one("#messages-scroll", VerticalScroll)
            messages_container.remove_children()
            self.messages.clear()
            self.conversation.clear()
            self.add_message("assistant", "Chat history cleared.")
        
        elif cmd == "/cd" and len(parts) > 1:
            path = parts[1]
            if self.shell_runner.change_directory(path):
                self.add_message("assistant", f"Changed directory to: {self.shell_runner.cwd}")
            else:
                self.add_message("assistant", f"Failed to change directory to: {path}")
        
        elif cmd == "/pwd":
            self.add_message("assistant", f"Current directory: {self.shell_runner.cwd}")
        
        elif cmd == "/ls":
            path = parts[1] if len(parts) > 1 else "."
            result = self.shell_runner.list_directory(path)
            self.add_command_output(result)
        
        elif cmd == "/settings":
            self.action_settings()
        
        elif cmd == "/plan":
            if len(parts) > 1:
                goal = parts[1]
                # Check if JSON steps provided
                if len(parts) > 2:
                    try:
                        steps = json.loads(parts[2])
                    except json.JSONDecodeError:
                        self.add_message("assistant", "Invalid steps JSON. Creating plan without steps.")
                        steps = []
                else:
                    # Create empty plan, AI will fill it
                    steps = []
                
                plan = self.plan_manager.create_plan(goal, steps)
                self._update_plan_widget()
                self.add_message("assistant", f"📋 Plan created: {goal}")
                
                # If AI should generate steps, send to AI
                if not steps:
                    asyncio.create_task(self.send_message(
                        f"Create a multi-step plan for: {goal}\n\n"
                        "Break this down into executable steps using the start_multistep_task tool."
                    ))
            else:
                self.add_message("assistant", "Usage: /plan <goal> [optional_steps_json]")
        
        elif cmd == "/step":
            if self.plan_manager.active_plan:
                asyncio.create_task(self._execute_next_step())
            else:
                self.add_message("assistant", "No active plan. Create one with /plan <goal>")
        
        elif cmd == "/modify":
            if len(parts) >= 3:
                try:
                    step_num = int(parts[1]) - 1  # Convert to 0-indexed
                    new_command = parts[2]
                    
                    plan = self.plan_manager.active_plan
                    if plan and 0 <= step_num < len(plan.steps):
                        modify_step(plan, step_num, new_command)
                        self._update_plan_widget()
                        self.add_message("assistant", f"Step {step_num + 1} modified to: {new_command}")
                    else:
                        self.add_message("assistant", f"Invalid step number: {parts[1]}")
                except ValueError:
                    self.add_message("assistant", f"Invalid step number: {parts[1]}")
            else:
                self.add_message("assistant", "Usage: /modify <step_num> <new_command>")
        
        elif cmd == "/skip":
            if self.plan_manager.active_plan:
                if len(parts) > 1:
                    try:
                        step_num = int(parts[1]) - 1
                        skip_step(self.plan_manager.active_plan, step_num)
                    except ValueError:
                        pass
                else:
                    self.plan_manager.skip_current_step()
                
                self._update_plan_widget()
                self.add_message("assistant", "Step skipped.")
            else:
                self.add_message("assistant", "No active plan.")
        
        elif cmd == "/add":
            if len(parts) >= 2:
                # Parse: /add <description> | <command>
                add_content = command[5:].strip()  # Remove "/add "
                if "|" in add_content:
                    desc, cmd_str = add_content.split("|", 1)
                    desc = desc.strip()
                    cmd_str = cmd_str.strip()
                else:
                    desc = add_content
                    cmd_str = "echo 'placeholder'"
                
                if self.plan_manager.add_step_after_current(desc, cmd_str):
                    self._update_plan_widget()
                    self.add_message("assistant", f"Step added: {desc}")
                else:
                    self.add_message("assistant", "Failed to add step. No active plan?")
            else:
                self.add_message("assistant", "Usage: /add <description> | <command>")
        
        elif cmd == "/verify":
            if self.plan_manager.active_plan:
                result = self.plan_manager.verify_completion()
                self.add_message("assistant", f"Verification:\n```json\n{json.dumps(result, indent=2)}\n```")
            else:
                self.add_message("assistant", "No active plan to verify.")
        
        elif cmd == "/clearplan":
            self.plan_manager.clear()
            self._update_plan_widget()
            self.add_message("assistant", "Plan cleared.")
        
        else:
            self.add_message("assistant", f"Unknown command: {cmd}. Type /help for available commands.")
    
    def on_plan_clear(self, message: PlanWidget.PlanClear):
        """Handle plan clear from widget."""
        self.plan_manager.clear()
    
    async def on_close(self):
        """Cleanup on close."""
        if self.ai_client:
            await self.ai_client.close()


def main():
    """Main entry point for the TUI."""
    # Print detection info before starting TUI
    from launcher import print_detection_results
    print_detection_results()
    print("\nStarting Rogius TUI...\n")
    
    app = RogiusTUI()
    app.run()


if __name__ == "__main__":
    main()
