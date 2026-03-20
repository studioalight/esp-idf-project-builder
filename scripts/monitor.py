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
from pathlib import Path

def get_bridge_uri():
    """Get WebSocket URI from environment or default"""
    import os
    host = os.environ.get('ESP_BRIDGE_HOST', 'esp32-bridge.tailbdd5a.ts.net')
    port = os.environ.get('ESP_BRIDGE_PORT', '5678')
    return f"wss://{host}:{port}"

async def monitor_serial(duration=None, grep=None, reset=False, stream=False, bridge_uri=None, timestamps=True):
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
                            if timestamps:
                                ts = data.get('timestamp', '')
                                if ts:
                                    # Parse ISO timestamp and format as HH:MM:SS.mmm
                                    from datetime import datetime
                                    try:
                                        dt = datetime.fromisoformat(ts)
                                        ts_str = dt.strftime('%H:%M:%S.%f')[:-3]
                                    except:
                                        ts_str = ts[:12]  # Fallback
                                    print(f"[{ts_str}] {text}", flush=stream)
                                else:
                                    print(text, flush=stream)
                            else:
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
    parser.add_argument('--no-timestamps', action='store_true', help='Hide timestamps')
    parser.add_argument('--stream', '-s', action='store_true', help='Stream output without buffering')
    args = parser.parse_args()
    
    bridge_uri = get_bridge_uri()
    
    print("ESP-IDF Serial Monitor")
    print(f"Bridge: {bridge_uri}\n")
    
    duration = None if args.forever else args.duration
    timestamps = not args.no_timestamps
    
    try:
        asyncio.run(monitor_serial(duration, args.grep, args.reset, args.stream, bridge_uri, timestamps))
    except KeyboardInterrupt:
        print("\n[Stopped by user]")
    
    print("\nMonitor ended.")

if __name__ == '__main__':
    main()
