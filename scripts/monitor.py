#!/usr/bin/env python3
"""
esp-idf monitor - Stream serial output from bridge
"""

import asyncio
import websockets
import json
import ssl
import argparse
import sys
import re
import yaml
from pathlib import Path

# Get skill root
SKILL_ROOT = Path(__file__).parent.parent

def load_chip_config():
    """Load chip configuration from YAML"""
    config_path = SKILL_ROOT / 'config' / 'chip-config.yaml'
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}

def get_bridge_uri(chip_config):
    """Get WebSocket URI from config"""
    bridge = chip_config.get('bridge', {})
    host = bridge.get('host', 'esp32-bridge.tailbdd5a.ts.net')
    port = bridge.get('ws_port', 5678)
    return f"wss://{host}:{port}"

async def monitor_serial(duration=None, grep=None, reset=False, stream=False, bridge_uri=None):
    """Monitor serial output"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    async with websockets.connect(bridge_uri, ssl=ssl_context, ping_interval=None) as ws:
        print(f"Connected to bridge", flush=stream)
        
        if reset:
            print("Resetting device...", flush=stream)
            await ws.send(json.dumps({'action': 'reset'}))
            await asyncio.sleep(1)
            print("Device reset complete\n", flush=stream)
        
        duration_str = f"{duration}s" if duration else "forever"
        print(f"Monitoring serial for {duration_str}...\n", flush=stream)
        
        start = asyncio.get_event_loop().time()
        
        while True:
            if duration and (asyncio.get_event_loop().time() - start > duration):
                print(f"\n[Monitor complete - {duration}s elapsed]", flush=stream)
                break
            
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1)
                
                try:
                    data = json.loads(msg)
                    if data.get('type') == 'serial':
                        text = data.get('text', '')
                        if grep and not re.search(grep, text):
                            continue
                        text = re.sub(r'[^\x20-\x7E\n\r]', '', text)
                        if text.strip():
                            print(text, flush=stream)
                            
                    elif data.get('type') == 'status':
                        status = data.get('connected', False)
                        port = data.get('port', 'none')
                        print(f"[BRIDGE] Connected: {status}, Port: {port}", flush=stream)
                        
                    elif data.get('type') == 'system':
                        msg_text = data.get('message', '')
                        if 'HTTP endpoint' not in msg_text:
                            print(f"[SYSTEM] {msg_text}", flush=stream)
                            
                except json.JSONDecodeError:
                    text = msg
                    if grep and not re.search(grep, text):
                        continue
                    if text.strip():
                        print(text, flush=stream)
                        
            except asyncio.TimeoutError:
                continue

def main():
    parser = argparse.ArgumentParser(description='Monitor serial output')
    parser.add_argument('--duration', '-d', type=int, default=15, help='Monitor duration in seconds')
    parser.add_argument('--grep', '-g', help='Filter output by pattern')
    parser.add_argument('--forever', '-f', action='store_true', help='Monitor forever')
    parser.add_argument('--reset', '-r', action='store_true', help='Reset device before monitoring')
    parser.add_argument('--stream', '-s', action='store_true', help='Stream output without buffering')
    args = parser.parse_args()
    
    chip_config = load_chip_config()
    bridge_uri = get_bridge_uri(chip_config)
    
    print("ESP-IDF Serial Monitor")
    print(f"Bridge: {bridge_uri}\n")
    
    duration = None if args.forever else args.duration
    
    try:
        asyncio.run(monitor_serial(duration, args.grep, args.reset, args.stream, bridge_uri))
    except KeyboardInterrupt:
        print("\n[Stopped by user]")
    
    print("\nMonitor ended.")

if __name__ == '__main__':
    main()
