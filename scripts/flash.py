#!/usr/bin/env python3
"""
esp-idf flash - Flash binaries via bridge WebSocket

Target-aware flashing with correct flash addresses from chip configuration.
"""

import asyncio
import websockets
import json
import ssl
import argparse
import sys
import os
from pathlib import Path

def get_bridge_uri():
    """Get WebSocket URI from environment or default"""
    import os
    host = os.environ.get('ESP_BRIDGE_HOST', 'esp32-bridge.tailbdd5a.ts.net')
    port = os.environ.get('ESP_BRIDGE_PORT', '5678')
    return f"wss://{host}:{port}"

def resolve_project_path(path_str):
    """Resolve project path"""
    path_str = os.path.expanduser(path_str)
    path = Path(path_str)
    
    if path.is_absolute():
        return path.resolve()
    
    if str(path).startswith('./'):
        return Path.cwd() / str(path)[2:]
    else:
        return Path.cwd() / path

def detect_target_from_build(build_dir):
    """Detect target from build artifacts"""
    # Try sdkconfig first
    sdkconfig = build_dir / 'config' / 'sdkconfig'
    if not sdkconfig.exists():
        sdkconfig = build_dir.parent / 'sdkconfig'
    
    if sdkconfig.exists():
        content = sdkconfig.read_text()
        for line in content.split('\n'):
            if line.startswith('CONFIG_IDF_TARGET='):
                return line.split('=')[1].strip('"')
    
    # Try to infer from binary names
    for bin_file in build_dir.glob('*.bin'):
        if 'esp32p4' in bin_file.name.lower():
            return 'esp32p4'
        elif 'esp32s3' in bin_file.name.lower():
            return 'esp32s3'
        elif 'esp32s2' in bin_file.name.lower():
            return 'esp32s2'
        elif 'esp32c3' in bin_file.name.lower():
            return 'esp32c3'
        elif 'esp32c6' in bin_file.name.lower():
            return 'esp32c6'
    
    return None

def get_default_baud(target):
    """Get default baud rate for target (hardcoded per-chip defaults)"""
    # ESP-IDF defaults - these are the standard values
    baud_map = {
        'esp32': 921600,
        'esp32s2': 921600,
        'esp32s3': 921600,
        'esp32c3': 921600,
        'esp32c6': 921600,
        'esp32p4': 921600,
    }
    return baud_map.get(target, 921600)

def get_build_files(build_dir, list_only=False):
    """Get list of flashable files from ESP-IDF build output (flash_args or flasher_args.json)
    
    Reads actual flash addresses from build artifacts - the ground truth from ESP-IDF.
    """
    flash_args = build_dir / 'flash_args'
    flasher_json = build_dir / 'flasher_args.json'
    files = []
    
    # Primary: flash_args file (ESP-IDF format: "0xADDR path/to/file.bin")
    if flash_args.exists():
        with open(flash_args) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('--'):
                    continue
                parts = line.split(maxsplit=1)
                if len(parts) >= 2 and parts[0].startswith('0x'):
                    addr = parts[0]
                    filepath = parts[1]
                    filename = os.path.basename(filepath)
                    
                    # For app binaries, prefer versioned version
                    if not any(x in filename.lower() for x in ['bootloader', 'partition', 'storage']):
                        name_base = filename.replace('.bin', '')
                        versioned = list(build_dir.glob(f"{name_base}-*.bin"))
                        versioned = [f for f in versioned if '-' in f.name and not f.name.startswith('.')]
                        if versioned:
                            versioned.sort(key=lambda f: os.path.getmtime(f), reverse=True)
                            filename = versioned[0].name
                    
                    files.append((filename, addr))
    
    # Fallback: flasher_args.json (alternative ESP-IDF format)
    elif flasher_json.exists():
        with open(flasher_json) as f:
            data = json.load(f)
            for entry in data.get('flash_files', []):
                addr = entry.get('addr', '0x10000')
                filepath = entry.get('path', '')
                filename = os.path.basename(filepath)
                
                if filename:
                    files.append((filename, addr))
    
    if list_only:
        return files
    
    # Return just the app binary for default flash (skip bootloader/partition/storage)
    app_files = [f for f in files if f[0].endswith('.bin') and not any(x in f[0].lower() for x in ['bootloader', 'partition', 'storage'])]
    return app_files[:1] if app_files else files[:1] if files else []

async def flash_file(ws, filename, address, baud=921600):
    """Flash single file"""
    print(f"\nFlashing {filename} at {address}...")
    
    await ws.send(json.dumps({
        'action': 'flash',
        'file': filename,
        'addr': address,
        'rate': baud
    }))
    
    while True:
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=120.0)
            data = json.loads(msg)
            
            if data.get('type') == 'output':
                print(f"  {data['data']}", end='')
            
            if data.get('type') == 'flash':
                status = data.get('status')
                if status == 'complete':
                    print(f"✓ {filename} complete")
                    return True
                elif status == 'error':
                    print(f"✗ Flash failed: {data.get('message')}", file=sys.stderr)
                    return False
                    
        except asyncio.TimeoutError:
            print(f"✗ Timeout", file=sys.stderr)
            return False
    
    return True

async def get_chip_id(ws):
    """Query chip ID from bridge"""
    await ws.send(json.dumps({'action': 'get_chip_id'}))
    
    try:
        msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
        data = json.loads(msg)
        
        if data.get('type') == 'chip_id':
            return {
                'chip_id': data.get('chip_id'),
                'mac': data.get('mac'),
                'target': data.get('target'),
                'status': data.get('status')
            }
        elif data.get('type') == 'error':
            return {'error': data.get('message', 'Unknown error')}
    except asyncio.TimeoutError:
        return {'error': 'Timeout waiting for chip ID'}
    
    return {'error': 'Invalid response'}

async def do_flash(files, baud=921600, reset_after=True, bridge_uri=None):
    """Flash files"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    async with websockets.connect(bridge_uri, ssl=ssl_context, ping_interval=None) as ws:
        print(f"Connected to bridge\n")
        
        # Enter bootloader
        await ws.send(json.dumps({'action': 'bootloader', 'enter_bootloader': True}))
        await asyncio.sleep(2)
        
        success = True
        for filename, address in files:
            if not await flash_file(ws, filename, address, baud):
                success = False
                break
            await asyncio.sleep(3.0)
        
        if reset_after and success:
            print("\nResetting device...")
            await ws.send(json.dumps({'reset': True}))
            await asyncio.sleep(1)
            print("✓ Device reset")
        
        return success

async def do_get_chip_id(bridge_uri=None):
    """Query chip ID from connected device via bridge"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    async with websockets.connect(bridge_uri, ssl=ssl_context, ping_interval=None) as ws:
        print("Connected to bridge")
        print("Querying chip ID...\n")
        
        result = await get_chip_id(ws)
        
        if 'error' in result:
            print(f"✗ Failed to get chip ID: {result['error']}")
            return False
        
        print(f"Chip ID:  {result.get('chip_id', 'N/A')}")
        print(f"MAC:      {result.get('mac', 'N/A')}")
        print(f"Target:   {result.get('target', 'N/A')}")
        print(f"Status:   {result.get('status', 'N/A')}")
        return True

def main():
    parser = argparse.ArgumentParser(description='Flash binaries via bridge')
    parser.add_argument('--project', '-p', help='Project directory (required for flash, optional for chip-id)')
    parser.add_argument('--target', '-t', help='Target chip (auto-detected if not specified)')
    parser.add_argument('--file', '-f', help='Specific file to flash')
    parser.add_argument('--addr', '-a', help='Address for specific file')
    parser.add_argument('--baud', '-b', type=int, help='Baud rate (auto-selected for target if not specified)')
    parser.add_argument('--list-files-to-flash', '-l', action='store_true', help='List available binaries without flashing')
    parser.add_argument('--no-reset', action='store_true', help='Skip device reset after flash')
    parser.add_argument('--chip-id', '-i', action='store_true', help='Query chip ID from connected device')
    args = parser.parse_args()
    
    # Bridge URI from environment or default
    bridge_uri = get_bridge_uri()
    
    # Handle chip ID query (no project required)
    if args.chip_id:
        success = asyncio.run(do_get_chip_id(bridge_uri=bridge_uri))
        sys.exit(0 if success else 1)
    
    # Project is required for flash operations
    if not args.project:
        print("Error: --project required (or use --chip-id to query device)", file=sys.stderr)
        sys.exit(1)
    
    # Resolve paths
    project_path = resolve_project_path(args.project)
    build_dir = project_path / 'build'
    
    if not build_dir.exists():
        print(f"Error: Build directory not found: {build_dir}", file=sys.stderr)
        sys.exit(1)
    
    # Detect or use specified target
    target = args.target
    if not target:
        target = detect_target_from_build(build_dir)
        if target:
            print(f"Auto-detected target: {target}")
        else:
            target = 'esp32s3'  # Sensible default
            print(f"Using default target: {target}")
    
    # Get baud rate (from args or target default)
    baud = args.baud if args.baud else get_default_baud(target)
    
    if args.list_files_to_flash:
        print(f"Flashable files in {build_dir}:")
        print(f"Target: {target}")
        print(f"(Addresses read from build/flash_args)")
        print()
        files = get_build_files(build_dir, list_only=True)
        for filename, addr in files:
            file_path = build_dir / filename
            if not file_path.exists():
                for subdir in ['bootloader', 'partition_table']:
                    alt_path = build_dir / subdir / filename
                    if alt_path.exists():
                        file_path = alt_path
                        break
            size = file_path.stat().st_size if file_path.exists() else 0
            print(f"  {filename:40s} at {addr:10s} ({size:,} bytes)")
        return
    
    # Determine what to flash
    if args.file:
        if not args.addr:
            print("Error: --addr required with --file", file=sys.stderr)
            sys.exit(1)
        files = [(args.file, args.addr)]
    else:
        files = get_build_files(build_dir)
        if not files:
            print("Error: No app binary found in build directory", file=sys.stderr)
            sys.exit(1)
    
    print(f"ESP-IDF Flash")
    print(f"Target: {target}")
    print(f"Files: {len(files)}")
    for filename, addr in files:
        print(f"  {filename} at {addr}")
    print(f"Baud rate: {baud}")
    print()
    
    success = asyncio.run(do_flash(files, baud=baud, reset_after=not args.no_reset, bridge_uri=bridge_uri))
    
    if success:
        print("\n✓ Flash complete!")
        print(f"Monitor with: esp-idf monitor")
    else:
        print("\n✗ Flash failed", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
