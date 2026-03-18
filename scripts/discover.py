#!/usr/bin/env python3
"""
Discover ESP32 device connected to bridge

Usage:
    esp-idf discover                    # Show connected device
    esp-idf discover --compare esp32s3  # Compare with expected target
"""

import asyncio
import json
import ssl
import websockets
import argparse
import sys
from pathlib import Path

def get_bridge_uri():
    """Get WebSocket URI from environment or default"""
    import os
    host = os.environ.get('ESP_BRIDGE_HOST', 'esp32-bridge.tailbdd5a.ts.net')
    port = os.environ.get('ESP_BRIDGE_PORT', '5678')
    return f"wss://{host}:{port}"

async def discover_device(bridge_uri):
    """Query bridge for connected device info"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    async with websockets.connect(bridge_uri, ssl=ssl_context, ping_interval=None) as ws:
        # Get chip ID
        await ws.send(json.dumps({'action': 'get_chip_id'}))
        
        # Wait for response (ignore serial/system messages)
        start_time = asyncio.get_event_loop().time()
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > 10.0:
                return {'error': 'Timeout waiting for device info'}
            
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                continue
            
            msg_type = data.get('type')
            
            if msg_type == 'chip_id':
                # Check if chip_id response contains an error
                if data.get('error'):
                    return {'error': data.get('error')}
                return {
                    'chip_id': data.get('chip_id'),
                    'mac': data.get('mac'),
                    'target': data.get('target'),
                    'status': data.get('status')
                }
            elif msg_type == 'error':
                return {'error': data.get('message', 'Unknown error')}
            # Ignore other message types

async def get_bridge_status(bridge_uri):
    """Get bridge status"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    async with websockets.connect(bridge_uri, ssl=ssl_context, ping_interval=None) as ws:
        await ws.send(json.dumps({'action': 'status'}))
        
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(msg)
            if data.get('type') == 'status':
                return {
                    'version': data.get('version'),
                    'git_hash': data.get('git_hash'),
                    'connected': data.get('connected'),
                    'port': data.get('port'),
                    'baudrate': data.get('baudrate'),
                    'chip': data.get('chip')
                }
        except:
            pass
        
        return None

def main():
    parser = argparse.ArgumentParser(description='Discover ESP32 device connected to bridge')
    parser.add_argument('--compare', '-c', help='Compare with expected target (e.g., esp32s3)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show verbose output')
    args = parser.parse_args()
    
    bridge_uri = get_bridge_uri()
    
    print("Discovering device on bridge...")
    print()
    
    # Get bridge status
    bridge_status = asyncio.run(get_bridge_status(bridge_uri))
    if bridge_status:
        print(f"Bridge:     v{bridge_status.get('version', 'unknown')} ({bridge_status.get('git_hash', 'unknown')[:7]})")
        print(f"Connected:  {bridge_status.get('connected', False)}")
        print(f"Port:       {bridge_status.get('port', 'N/A')}")
        print(f"Baud:       {bridge_status.get('baudrate', 'N/A')}")
        print()
    
    # Get device info
    device = asyncio.run(discover_device(bridge_uri))
    
    if device is None or 'error' in device:
        print(f"✗ No device detected: {device['error']}")
        print()
        print("Possible causes:")
        print("  - Device not connected to bridge")
        print("  - Device in bootloader mode")
        print("  - USB cable disconnected")
        sys.exit(1)
    
    print("Device Info:")
    print(f"  Target:   {device.get('target', 'N/A')}")
    print(f"  MAC:      {device.get('mac', 'N/A')}")
    print(f"  Chip ID:  {device.get('chip_id', 'N/A')}")
    print(f"  Status:   {device.get('status', 'N/A')}")
    print()
    
    # Compare with expected target
    if args.compare:
        expected = args.compare.lower().replace('-', '')
        actual = device.get('target', '').lower().replace('-', '')
        
        if expected == actual:
            print(f"✓ Device matches expected target: {args.compare}")
            sys.exit(0)
        else:
            print(f"⚠ Device mismatch!")
            print(f"  Expected: {args.compare}")
            print(f"  Actual:   {device.get('target', 'N/A')}")
            print()
            print("Options:")
            print(f"  1. Connect the correct device ({args.compare})")
            print(f"  2. Build for {device.get('target', 'unknown')} instead")
            print(f"  3. Use --target {device.get('target', 'unknown')} to override")
            sys.exit(2)
    
    sys.exit(0)

if __name__ == '__main__':
    main()
