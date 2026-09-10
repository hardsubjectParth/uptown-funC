import os
import socket
from datetime import datetime, timezone


class NetworkMonitor:
    """Small, dependency-free egress status surface for air-gapped deployments.

    It does not enforce anything -- egress is blocked by the deployment (a
    container with no outbound route, a firewall, an offline host). This just
    reports the intended policy and any outbound connections the app itself
    observed, so an operator or a demo can show "nothing leaves the box".
    """

    def __init__(self):
        self.events = []
        self.cloud_disabled = os.getenv('OLLAMA_NO_CLOUD', 'true').lower() in {'1', 'true', 'yes'}
        self.network_forbidden = os.getenv('NETWORK_FORBIDDEN', 'false').lower() in {'1', 'true', 'yes'}

    def record(self, destination, port, status='observed'):
        self.events.append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'destination': destination,
            'port': port,
            'status': status,
        })
        self.events = self.events[-100:]

    def check(self):
        cloud_endpoint = os.getenv('OLLAMA_CLOUD_ENDPOINT', '').strip()
        cloud_configured = bool(cloud_endpoint)
        return {
            'network_forbidden': self.network_forbidden,
            'ollama_cloud_disabled': self.cloud_disabled,
            'cloud_endpoint_configured': cloud_configured,
            'egress_policy': 'forbidden' if self.network_forbidden else 'operator-enforced',
            'outbound_events': list(self.events),
            'ok': self.cloud_disabled and not cloud_configured,
        }

    def probe_local(self, host='127.0.0.1', port=11434, timeout=0.25):
        """Confirm a local service (Ollama by default) is reachable on loopback."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                self.record(host, port, 'local_allowed')
                return True
        except OSError:
            return False


network_monitor = NetworkMonitor()
