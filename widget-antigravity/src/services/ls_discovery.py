"""
Language Server Discovery Service for Antigravity Quota Monitor.
Discovers running language_server instances, extracts CSRF tokens and active HTTP/Connect-RPC ports.
"""
import re
import os
import glob
import psutil
import requests
from typing import Optional, Tuple, List, Dict


class LSInstance:
    """Represents a discovered Language Server instance."""
    def __init__(self, pid: int, port: int, csrf_token: str, is_active: bool = False):
        self.pid = pid
        self.port = port
        self.csrf_token = csrf_token
        self.is_active = is_active

    def __repr__(self):
        return f"LSInstance(pid={self.pid}, port={self.port}, csrf={self.csrf_token[:8]}...)"


class LSDiscovery:
    """Discovers Antigravity Language Server endpoints and auth tokens."""

    def __init__(self):
        self._cached_instance: Optional[LSInstance] = None

    def find_active_server(self, force_refresh: bool = False) -> Optional[LSInstance]:
        """
        Finds a working Language Server instance.
        Tests cached instance first for maximum speed; if invalid, falls back to process scanning and logs.
        """
        if self._cached_instance:
            if self._test_connection(self._cached_instance.port, self._cached_instance.csrf_token):
                return self._cached_instance

        # 1. Process Discovery (Primary Method)
        try:
            instances = self._discover_from_processes()
            for inst in instances:
                if self._test_connection(inst.port, inst.csrf_token):
                    inst.is_active = True
                    self._cached_instance = inst
                    return inst
        except Exception:
            pass

        # 2. Fallback: Log files scanning
        try:
            fallback_inst = self._discover_from_logs()
            if fallback_inst and self._test_connection(fallback_inst.port, fallback_inst.csrf_token):
                fallback_inst.is_active = True
                self._cached_instance = fallback_inst
                return fallback_inst
        except Exception:
            pass

        self._cached_instance = None
        return None

    def _discover_from_processes(self) -> List[LSInstance]:
        """Scans running processes for language_server binaries and extracts port/csrf."""
        candidates: List[LSInstance] = []

        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = proc.info.get('name', '') or ''
                    name = name.lower()
                    cmdline = proc.info.get('cmdline') or []
                    
                    # Match Antigravity language server process names
                    if not any(k in name for k in ['language_server', 'antigravity']):
                        cmdline_str = " ".join(cmdline).lower()
                        if 'language_server' not in cmdline_str:
                            continue

                    csrf_token = self._extract_csrf_from_cmdline(cmdline)
                    if not csrf_token:
                        continue

                    # Find open listening TCP ports for this PID
                    listening_ports = []
                    try:
                        connections = proc.net_connections(kind='tcp')
                        for conn in connections:
                            if conn.status == psutil.CONN_LISTEN and conn.laddr:
                                listening_ports.append(conn.laddr.port)
                    except Exception:
                        pass

                    for port in listening_ports:
                        candidates.append(LSInstance(proc.pid, port, csrf_token))

                except Exception:
                    continue
        except Exception:
            pass

        return candidates

    def _extract_csrf_from_cmdline(self, cmdline: List[str]) -> Optional[str]:
        """Extracts --csrf_token value from command line arguments list."""
        for i, arg in enumerate(cmdline):
            if arg in ('--csrf_token', '-csrf_token') and i + 1 < len(cmdline):
                return cmdline[i + 1]
            if arg.startswith('--csrf_token='):
                return arg.split('=', 1)[1]
            if arg.startswith('-csrf_token='):
                return arg.split('=', 1)[1]

        # Regex fallback on full command string
        full = " ".join(cmdline)
        match = re.search(r'--csrf_token[=\s]+([a-f0-9\-]{36})', full, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _discover_from_logs(self) -> Optional[LSInstance]:
        """Scans Antigravity IDE and desktop app logs for ports and tokens."""
        appdata = os.environ.get('APPDATA', '')
        log_dirs = [
            os.path.join(appdata, 'Antigravity IDE', 'logs'),
            os.path.join(appdata, 'Antigravity', 'logs'),
        ]

        # Look for most recent ls-main.log
        latest_logs = []
        for base_dir in log_dirs:
            if not os.path.exists(base_dir):
                continue
            for root, _, files in os.walk(base_dir):
                for f in files:
                    if f in ('ls-main.log', 'language_server.log'):
                        full_path = os.path.join(root, f)
                        try:
                            mtime = os.path.getmtime(full_path)
                            latest_logs.append((mtime, full_path))
                        except OSError:
                            pass

        latest_logs.sort(key=lambda x: x[0], reverse=True)

        for _, log_path in latest_logs[:5]:
            csrf_token = None
            ports = []
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    # Read last 300 lines or first 300 lines
                    lines = f.readlines()
                    search_lines = lines[:100] + lines[-200:]
                    for line in search_lines:
                        if not csrf_token:
                            csrf_match = re.search(r'--csrf_token[=\s]+([a-f0-9\-]{36})', line, re.IGNORECASE)
                            if csrf_match:
                                csrf_token = csrf_match.group(1)
                        
                        port_match = re.search(r'listening on random port at (\d+) for HTTP', line, re.IGNORECASE)
                        if port_match:
                            ports.append(int(port_match.group(1)))

                if csrf_token and ports:
                    for port in reversed(ports):
                        if self._test_connection(port, csrf_token):
                            return LSInstance(pid=0, port=port, csrf_token=csrf_token)
            except Exception:
                continue

        return None

    def _test_connection(self, port: int, csrf_token: str) -> bool:
        """Sends a quick test request to verify if endpoint responds with 200 OK."""
        try:
            url = f"http://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/GetUserStatus"
            headers = {
                "Content-Type": "application/json",
                "x-codeium-csrf-token": csrf_token,
            }
            resp = requests.post(url, headers=headers, json={}, timeout=1.5)
            if resp.status_code == 200:
                data = resp.json()
                return "userStatus" in data
        except Exception:
            pass
        return False
