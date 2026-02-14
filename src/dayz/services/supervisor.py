#!/usr/bin/env python3
"""
DayZ Server Supervisor - Socket-Based Control

- Communicates with API via Unix domain socket
- Handles graceful shutdown on SIGTERM/SIGINT

Control Interface:
- /control/supervisor.sock: Unix socket for commands (replaces command file)
- /control/state.json: Current state (kept for backward compatibility)
- /control/supervisor.pid: Supervisor PID for health checks
"""

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from dayz.config.models import ServerCommand, ServerState
from dayz.config.paths import (
    CONTROL_DIR,
    MAINTENANCE_FILE,
    MOD_PARAM_FILE,
    SERVER_BINARY,
    SERVER_FILES,
    SERVER_MOD_PARAM_FILE,
    SERVER_PARAMS_FILE,
    SOCKET_PATH,
    STATE_FILE,
    SUPERVISOR_PID,
)
from dayz.core.params import compose_server_params

# =============================================================================
# Configuration
# =============================================================================

# Paths (adjust these to match your actual paths module)


# Restart behavior
MAX_RAPID_RESTARTS = 5
RAPID_RESTART_WINDOW = 300  # seconds
RESTART_DELAY_BASE = 2
RESTART_DELAY_MAX = 60


@dataclass
class SupervisorState:
    """Current supervisor state"""

    state: str = ServerState.STOPPED.value
    pid: int | None = None
    started_at: str | None = None
    uptime_seconds: int = 0
    restart_count: int = 0
    last_exit_code: int | None = None
    last_crash_time: str | None = None
    auto_restart: bool = True
    maintenance: bool = False
    message: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_json(self) -> str:
        self.updated_at = datetime.now().isoformat()
        return json.dumps(asdict(self), indent=2)

    def to_dict(self) -> dict:
        self.updated_at = datetime.now().isoformat()
        return asdict(self)


@dataclass
class CommandResponse:
    """Response to API commands"""

    success: bool
    message: str
    state: dict | None = None

    def to_json(self) -> str:
        return json.dumps({"success": self.success, "message": self.message, "state": self.state})


# =============================================================================
# Supervisor
# =============================================================================


class DayZSupervisor:
    """Manages DayZServer process lifecycle"""

    def __init__(self) -> None:
        self.state = SupervisorState()
        self.process: subprocess.Popen | None = None
        self.should_run = True
        self.restart_times: list[float] = []
        self.state_lock = threading.Lock()

        # Socket server
        self.socket_server: socket.socket | None = None
        self.socket_thread: threading.Thread | None = None

        # Ensure control directory exists
        CONTROL_DIR.mkdir(parents=True, exist_ok=True)

        # Initialize maintenance mode
        if MAINTENANCE_FILE.exists():
            self.state.maintenance = True
            self.state.state = ServerState.MAINTENANCE.value
            self.state.message = "Maintenance mode enabled"
            self.state.auto_restart = False

        # Write supervisor PID
        SUPERVISOR_PID.write_text(str(os.getpid()))

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum: int, frame: object) -> None:
        """Handle shutdown signals"""
        sig_name = signal.Signals(signum).name
        self.log(f"Received {sig_name}, initiating shutdown...")
        self.should_run = False
        self._stop_server(graceful=True)

    def log(self, message: str) -> None:
        """Log with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [Supervisor] {message}", flush=True)

    def _write_state(self) -> None:
        """Write current state to state.json (for backward compatibility/monitoring)"""
        with self.state_lock:
            # Update uptime if running
            if self.state.state == ServerState.RUNNING.value and self.state.started_at:
                try:
                    started = datetime.fromisoformat(self.state.started_at)
                    self.state.uptime_seconds = int((datetime.now() - started).total_seconds())
                except Exception:
                    pass
            else:
                # Clear uptime when not running
                self.state.uptime_seconds = 0
                if self.state.state not in (ServerState.STARTING.value, ServerState.STOPPING.value):
                    self.state.started_at = None

            try:
                STATE_FILE.write_text(self.state.to_json())
            except Exception as e:
                self.log(f"Failed to write state: {e}")

    def _is_maintenance(self) -> bool:
        """Check if maintenance mode is active"""
        return self.state.maintenance

    def _set_maintenance(self, enabled: bool) -> None:
        """Toggle maintenance mode"""
        with self.state_lock:
            self.state.maintenance = enabled
            if enabled:
                self.state.state = ServerState.MAINTENANCE.value
                self.state.message = "Maintenance mode enabled"
                MAINTENANCE_FILE.touch(exist_ok=True)
            else:
                if self.state.state == ServerState.MAINTENANCE.value:
                    self.state.state = ServerState.STOPPED.value
                    self.state.started_at = None
                self.state.message = "Maintenance mode disabled"
                MAINTENANCE_FILE.unlink(missing_ok=True)
        self._write_state()

    def _build_server_command(self) -> list[str]:
        """Build DayZServer command line"""
        cmd = [str(SERVER_BINARY)]

        # Read mod parameters
        if MOD_PARAM_FILE.exists():
            mod_param = MOD_PARAM_FILE.read_text().strip()
            if mod_param:
                cmd.append(mod_param)

        if SERVER_MOD_PARAM_FILE.exists():
            server_param = SERVER_MOD_PARAM_FILE.read_text().strip()
            if server_param:
                cmd.append(server_param)

        # Server parameters
        server_params_file = SERVER_PARAMS_FILE
        params = ""
        if server_params_file.exists():
            try:
                params = server_params_file.read_text().strip()
            except Exception:
                params = ""
        if not params:
            params = compose_server_params()

        cmd.extend(params.split())
        return cmd

    def _check_rapid_restarts(self) -> bool:
        """Check if we're in a rapid restart loop"""
        now = time.time()
        self.restart_times = [t for t in self.restart_times if now - t < RAPID_RESTART_WINDOW]

        if len(self.restart_times) >= MAX_RAPID_RESTARTS:
            self.log(f"Too many restarts in {RAPID_RESTART_WINDOW}s, disabling auto-restart")
            with self.state_lock:
                self.state.auto_restart = False
                self.state.state = ServerState.DISABLED.value
                self.state.started_at = None
                self.state.message = f"Auto-restart disabled: {MAX_RAPID_RESTARTS} crashes"
            return False

        self.restart_times.append(now)
        return True

    def _start_server(self) -> bool:
        """Start the DayZ server process"""
        if self._is_maintenance():
            with self.state_lock:
                self.state.state = ServerState.MAINTENANCE.value
                self.state.message = "Maintenance mode active, start blocked"
            self._write_state()
            self.log("Start request ignored: maintenance mode enabled")
            return False

        if not SERVER_BINARY.exists():
            with self.state_lock:
                self.state.state = ServerState.STOPPED.value
                self.state.started_at = None
                self.state.message = "DayZServer binary not found"
            self.log(self.state.message)
            self._write_state()
            return False

        if self.process and self.process.poll() is None:
            self.log("Server already running")
            return True

        with self.state_lock:
            self.state.state = ServerState.STARTING.value
            self.state.message = "Starting server..."
        self._write_state()

        cmd = self._build_server_command()
        self.log(f"Starting: {' '.join(cmd[:3])}...")

        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=str(SERVER_FILES),
                stdout=sys.stdout,
                stderr=sys.stderr,
            )

            time.sleep(2)

            if self.process.poll() is not None:
                exit_code = self.process.returncode
                with self.state_lock:
                    self.state.state = ServerState.CRASHED.value
                    self.state.started_at = None
                    self.state.last_exit_code = exit_code
                    self.state.message = f"Server exited immediately with code {exit_code}"
                self.log(self.state.message)
                self._write_state()
                return False

            with self.state_lock:
                self.state.state = ServerState.RUNNING.value
                self.state.pid = self.process.pid
                self.state.started_at = datetime.now().isoformat()
                self.state.uptime_seconds = 0
                self.state.message = "Server running"
            self.log(f"Server started with PID {self.process.pid}")
            self._write_state()
            return True

        except Exception as e:
            with self.state_lock:
                self.state.state = ServerState.CRASHED.value
                self.state.message = f"Failed to start: {e}"
            self.log(self.state.message)
            self._write_state()
            return False

    def _stop_server(self, graceful: bool = True) -> bool:
        """Stop the DayZ server process"""
        if not self.process:
            with self.state_lock:
                self.state.state = ServerState.STOPPED.value
                self.state.pid = None
                self.state.started_at = None
                self.state.uptime_seconds = 0
                self.state.message = "Server not running"
            self._write_state()
            return True

        # Store process reference to avoid race condition with self.process = None
        process = self.process

        if process.poll() is not None:
            with self.state_lock:
                self.state.state = ServerState.STOPPED.value
                self.state.pid = None
                self.state.started_at = None
                self.state.uptime_seconds = 0
                self.state.last_exit_code = process.returncode
            self._write_state()
            return True

        with self.state_lock:
            self.state.state = ServerState.STOPPING.value
            self.state.message = "Stopping server..."
        self._write_state()

        pid = process.pid
        self.log(f"Stopping server (PID {pid})...")

        try:
            if graceful:
                process.terminate()
                for _ in range(30):
                    if process.poll() is not None:
                        break
                    time.sleep(1)

            if process.poll() is None:
                self.log("Graceful shutdown timed out, sending SIGKILL...")
                process.kill()
                process.wait(timeout=5)

            exit_code = process.returncode
            with self.state_lock:
                self.state.state = ServerState.STOPPED.value
                self.state.pid = None
                self.state.started_at = None
                self.state.uptime_seconds = 0
                self.state.last_exit_code = exit_code
                self.state.message = f"Server stopped (exit code: {exit_code})"
            self.log(self.state.message)
            self._write_state()
            return True

        except Exception as e:
            self.log(f"Error stopping server: {e}")
            with self.state_lock:
                self.state.message = f"Stop error: {e}"
            self._write_state()
            return False

    def _handle_command(self, cmd: ServerCommand) -> CommandResponse:
        """Process a command and return response"""
        self.log(f"Received command: {cmd.value}")

        try:
            if cmd == ServerCommand.STATUS:
                with self.state_lock:
                    return CommandResponse(
                        success=True, message="Status retrieved", state=self.state.to_dict()
                    )

            elif cmd == ServerCommand.START:
                if self._is_maintenance():
                    return CommandResponse(
                        success=False,
                        message="Cannot start: maintenance mode active",
                        state=self.state.to_dict(),
                    )

                with self.state_lock:
                    if self.state.state in (ServerState.RUNNING.value, ServerState.STARTING.value):
                        return CommandResponse(
                            success=True,
                            message="Server already running",
                            state=self.state.to_dict(),
                        )

                self.state.auto_restart = True
                self.restart_times.clear()
                success = self._start_server()

                return CommandResponse(
                    success=success,
                    message="Server started" if success else "Failed to start server",
                    state=self.state.to_dict(),
                )

            elif cmd == ServerCommand.STOP:
                self.state.auto_restart = False
                success = self._stop_server()

                return CommandResponse(
                    success=success,
                    message="Server stopped" if success else "Failed to stop server",
                    state=self.state.to_dict(),
                )

            elif cmd == ServerCommand.RESTART:
                if self._is_maintenance():
                    return CommandResponse(
                        success=False,
                        message="Cannot restart: maintenance mode active",
                        state=self.state.to_dict(),
                    )

                self._stop_server()
                time.sleep(2)
                self.state.auto_restart = True
                success = self._start_server()

                with self.state_lock:
                    self.state.restart_count += 1

                return CommandResponse(
                    success=success,
                    message="Server restarted" if success else "Restart failed",
                    state=self.state.to_dict(),
                )

            elif cmd == ServerCommand.ENABLE:
                with self.state_lock:
                    self.state.auto_restart = True
                    self.restart_times.clear()
                    self.state.state = ServerState.STOPPED.value
                    self.state.message = "Auto-restart enabled"
                self._write_state()

                return CommandResponse(
                    success=True, message="Auto-restart enabled", state=self.state.to_dict()
                )

            elif cmd == ServerCommand.DISABLE:
                with self.state_lock:
                    self.state.auto_restart = False
                    self.state.message = "Auto-restart disabled"
                self._write_state()

                return CommandResponse(
                    success=True, message="Auto-restart disabled", state=self.state.to_dict()
                )

            elif cmd == ServerCommand.MAINTENANCE:
                self.state.auto_restart = False
                self._stop_server()
                self._set_maintenance(True)

                return CommandResponse(
                    success=True, message="Maintenance mode enabled", state=self.state.to_dict()
                )

            elif cmd == ServerCommand.RESUME:
                self._set_maintenance(False)
                self.state.auto_restart = True

                return CommandResponse(
                    success=True, message="Maintenance mode disabled", state=self.state.to_dict()
                )

            else:
                return CommandResponse(
                    success=False, message=f"Unknown command: {cmd}", state=self.state.to_dict()
                )

        except Exception as e:
            self.log(f"Error handling command {cmd}: {e}")
            return CommandResponse(success=False, message=f"Error: {e}", state=self.state.to_dict())

    def _socket_handler(self, client_socket: socket.socket, client_addr: str) -> None:
        """Handle a single socket connection"""
        try:
            # Receive command (max 1KB should be plenty)
            data = client_socket.recv(1024).decode("utf-8").strip()

            if not data:
                return

            try:
                # Parse JSON command
                request = json.loads(data)
                cmd_str = request.get("command", "").lower()

                # Validate command
                try:
                    cmd = ServerCommand(cmd_str)
                except ValueError:
                    response = CommandResponse(success=False, message=f"Unknown command: {cmd_str}")
                    client_socket.sendall(response.to_json().encode("utf-8"))
                    return

                # Execute command
                response = self._handle_command(cmd)
                client_socket.sendall(response.to_json().encode("utf-8"))

            except json.JSONDecodeError:
                response = CommandResponse(success=False, message="Invalid JSON")
                client_socket.sendall(response.to_json().encode("utf-8"))

        except Exception as e:
            self.log(f"Socket handler error: {e}")
        finally:
            client_socket.close()

    def _socket_server_loop(self) -> None:
        """Main socket server loop"""
        # Remove old socket file if it exists
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()

        # Create Unix domain socket
        self.socket_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket_server.bind(str(SOCKET_PATH))
        self.socket_server.listen(5)

        # Make socket accessible
        SOCKET_PATH.chmod(0o666)

        self.log(f"Socket server listening on {SOCKET_PATH}")

        while self.should_run:
            try:
                self.socket_server.settimeout(1.0)  # Check should_run periodically
                client_socket, client_addr = self.socket_server.accept()

                # Handle each connection in a separate thread
                handler_thread = threading.Thread(
                    target=self._socket_handler, args=(client_socket, client_addr), daemon=True
                )
                handler_thread.start()

            except TimeoutError:
                continue
            except Exception as e:
                if self.should_run:
                    self.log(f"Socket server error: {e}")
                break

    def run(self) -> None:
        """Main supervisor loop"""
        self.log("Supervisor starting...")

        with self.state_lock:
            self.state.message = "Supervisor ready"
        self._write_state()

        # Start socket server in background thread
        self.socket_thread = threading.Thread(target=self._socket_server_loop, daemon=True)
        self.socket_thread.start()

        # Auto-start server if binary exists and not in maintenance
        if SERVER_BINARY.exists():
            if self._is_maintenance():
                self.log("Maintenance mode enabled, skipping auto-start")
                with self.state_lock:
                    self.state.state = ServerState.MAINTENANCE.value
                    self.state.message = "Maintenance mode enabled"
                self._write_state()
            else:
                self.log("Starting server...")
                self._start_server()
        else:
            self.log("Server binary not found, waiting for install...")
            with self.state_lock:
                self.state.message = "Waiting for server install"
            self._write_state()

        # Main monitoring loop
        while self.should_run:
            # Monitor server process
            if self.process and self.process.poll() is not None:
                exit_code = self.process.returncode

                with self.state_lock:
                    self.state.last_exit_code = exit_code
                    self.state.pid = None
                    self.state.started_at = None

                    if exit_code == 0:
                        self.log("Server exited normally")
                        self.state.state = ServerState.STOPPED.value
                        self.state.message = "Server stopped normally"
                    else:
                        self.log(f"Server crashed with exit code {exit_code}")
                        self.state.state = ServerState.CRASHED.value
                        self.state.last_crash_time = datetime.now().isoformat()
                        self.state.message = f"Server crashed (exit code: {exit_code})"

                self._write_state()
                self.process = None

                # Auto-restart logic
                if self.state.auto_restart and exit_code != 0 and not self._is_maintenance():
                    if self._check_rapid_restarts():
                        delay = min(
                            RESTART_DELAY_BASE * (2 ** len(self.restart_times)), RESTART_DELAY_MAX
                        )
                        self.log(f"Auto-restarting in {delay}s...")
                        with self.state_lock:
                            self.state.message = f"Restarting in {delay}s..."
                        self._write_state()
                        time.sleep(delay)
                        self._start_server()
                        with self.state_lock:
                            self.state.restart_count += 1
                    else:
                        self._write_state()
                elif self._is_maintenance():
                    with self.state_lock:
                        self.state.state = ServerState.MAINTENANCE.value
                        self.state.message = "Maintenance mode enabled"
                    self._write_state()

            # Update state periodically
            self._write_state()
            time.sleep(1)

        # Cleanup
        self.log("Supervisor shutting down...")
        self._stop_server(graceful=True)

        # Close socket
        if self.socket_server:
            self.socket_server.close()
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()

        SUPERVISOR_PID.unlink(missing_ok=True)
        self.log("Supervisor stopped")


class DayZSupervisorClient:
    """Client for communicating with supervisor via Unix socket"""

    def __init__(self, socket_path: Path | None = None):
        self.socket_path = socket_path or SOCKET_PATH

    def _send_command(self, command: str, timeout: float = 5.0) -> CommandResponse:
        """Send command to supervisor and get response"""
        if not self.socket_path.exists():
            return CommandResponse(
                success=False,
                message="Supervisor not running (socket not found)",
                state=None,
            )

        try:
            # Connect to socket
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect(str(self.socket_path))

            # Send command as JSON
            request = json.dumps({"command": command})
            sock.sendall(request.encode("utf-8"))

            # Receive response (up to 4KB should be plenty)
            response_data = sock.recv(4096).decode("utf-8")
            sock.close()

            # Parse JSON response
            return CommandResponse(**json.loads(response_data))

        except TimeoutError:
            return CommandResponse(
                success=False, message="Supervisor request timed out", state=None
            )
        except OSError as e:
            return CommandResponse(
                success=False, message=f"Socket communication error: {e}", state=None
            )
        except json.JSONDecodeError as e:
            return CommandResponse(
                success=False,
                message=f"Invalid response from supervisor: {e}",
                state=None,
            )
        except Exception as e:
            return CommandResponse(success=False, message=f"Unexpected error: {e}", state=None)


def main() -> None:
    supervisor = DayZSupervisor()
    supervisor.run()


if __name__ == "__main__":
    main()
