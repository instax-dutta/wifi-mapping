"""Optional MQTT publisher for live state.

No-op and import-safe when paho-mqtt is not installed, so the core system never
depends on it. Adapted from RuView's MQTT integration idea.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional


class Publisher:
    def __init__(self, host: Optional[str] = None, port: int = 1883,
                 topic: str = "wifimap/state", client_id: str = "wifimap"):
        self.topic = topic
        self.available = False
        self.client = None
        if not host:
            return
        try:
            import paho.mqtt.client as mqtt  # type: ignore
            self.client = mqtt.Client(client_id)
            self.client.connect(host, port, 60)
            self.client.loop_start()
            self.available = True
        except Exception:
            self.available = False

    def publish(self, state: Dict[str, Any]) -> bool:
        if not self.available or self.client is None:
            return False
        try:
            self.client.publish(self.topic, json.dumps(state))
            return True
        except Exception:
            return False

    def close(self) -> None:
        if self.client is not None:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
        self.available = False
