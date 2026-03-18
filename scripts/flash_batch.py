#!/usr/bin/env python3
"""
esp-idf flash-batch - Flash multiple binaries in one atomic operation

Target-aware batch flashing using esptool's native multi-file write_flash.
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
    sdkconfig = build_dir / 'config' / 'sdkconfig'
    if not sdkconfig.exists():
        sdkconfig = build_dir.parent / 'sdkconfig'
    
    if sdkconfig.exists():
        content = sdkconfig.read_text()
        for line in content.split('\n'):
            if line.startswith('CONFIG_IDF_TARGET='):
                return line.split('=')[1].strip('"')
    
    for bin_file in build_dir.glob('*.bin'):
        name_lower = bin_file.name.lower()
        if 'esp32p4' in name_lower:
            return 'esp32p4'
        elif 'esp32s3' in name_lower:
            return 'esp32s3'
        elif 'esp32s2' in name_lower:
            return 'esp32s2'
        elif 'esp32c3' in name_lower:
            return 'esp32c3'
        elif 'esp32c6' in name_lower:
            return 'esp32c6'
        elif 'esp32' in name_lower:
            return 'esp32'
    
    return None

def get_default_baud(target):
    """Get default baud rate for target (hardcoded per-chip defaults)"""
    baud_map = {
        'esp32': 921600,
        'esp32s2': 921600,
        'esp32s3': 921600,
        'esp32c3': 921600,
        'esp32c6': 921600,
        'esp32p4': 921600,
    }
    return baud_map.get(target, 921600)

def get_flash_files_from_manifest(build_dir):
    """Get ordered list of files to flash from ESP-IDF build artifacts (flash_args)
    
    Reads actual flash addresses from build/flash_args - the ground truth from ESP-IDF.
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
                    
                    category = 'app'
                    if 'bootloader' in filename.lower():
                        category = 'bootloader'
                    elif 'partition' in filename.lower():
                        category = 'partition'
                    elif 'storage' in filename.lower():
                        category = 'storage'
                    
                    files.append({
                        'filename': filename,
                        'addr': addr,
                        'category': category
                    })
        
        # Sort by address (lowest first) to ensure correct flash order
        files.sort(key=lambda f: int(f['addr'], 16))
    
    # Fallback: flasher_args.json (alternative ESP-IDF format)
    elif flasher_json.exists():
        with open(flasher_json) as f:
            data = json.load(f)
            for entry in data.get('flash_files', []):
                addr = entry.get('addr', '0x10000')
                filepath = entry.get('path', '')
                filename = os.path.basename(filepath)
                
                if filename:
                    category = 'app'
                    if 'bootloader' in filename.lower():
                        category = 'bootloader'
                    elif 'partition' in filename.lower():
                        category = 'partition'
                    elif 'storage' in filename.lower():
                        category = 'storage'
                    
                    files.append({
                        'filename': filename,
                        'addr': addr,
                        'category': category
                    })
        
        # Sort by address (lowest first) to ensure correct flash order
        files.sort(key=lambda f: int(f['addr'], 16))
    
    return files
    
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
                if not any(x in filename.lower() for x in ['bootloader', 'partition']):
                    name_base = filename.replace('.bin', '')
                    versioned = list(build_dir.glob(f"{name_base}-*.bin"))
                    versioned = [f for f in versioned if '-' in f.name and not f.name.startswith('.')]
                    if versioned:
                        versioned.sort(key=lambda f: os.path.getmtime(f), reverse=True)
                        filename = versioned[0].name
                
                category = 'app'
                if 'bootloader' in filename.lower():
                    category = 'bootloader'
                elif 'partition' in filename.lower():
                    category = 'partition'
                elif 'storage' in filename.lower():
                    category = 'storage'
                
                files.append({
                    'filename': filename,
                    'addr': addr,
                    'category': category
                })
    
    return files

def scan_for_storage(build_dir):
    """Scan for storage.bin if not in manifest"""
    storage = build_dir / 'storage.bin'
    if storage.exists():
        return {'filename': 'storage.bin', 'addr': '0x910000', 'category': 'storage'}
    return None

async def flash_batch(ws, files, baud=1500000, reset_after=True, verbose=False):
    """Send batch flash command to bridge"""
    await ws.send(json.dumps({
        'action': 'flash_batch',
        'files': files,
        'rate': baud,
        'reset_after': reset_after,
        'verify': True
    }))
    
    file_count = len(files)
    current_file = 0
    current_file_name = None
    esptool_output = []
    
    while True:
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=180.0)
            
            # Verbose: show raw message
            if verbose:
                print(f"[RAW] {msg[:200]}{'...' if len(msg) > 200 else ''}")
            
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                if verbose:
                    print(f"[NON-JSON] {msg[:100]}")
                continue
            
            msg_type = data.get('type')
            
            # Handle esptool stdout output
            if msg_type == 'output':
                output_data = data.get('data', '')
                esptool_output.append(output_data)
                print(f"  {output_data}", end='')
            
            # Handle esptool stderr
            elif msg_type == 'error_output':
                error_data = data.get('data', '')
                esptool_output.append(f"[stderr] {error_data}")
                print(f"  [stderr] {error_data}", end='', file=sys.stderr)
            
            # Handle system/debug messages
            elif msg_type == 'system':
                if verbose:
                    print(f"[SYSTEM] {data.get('message', '')}")
            
            # Handle flash_batch status messages
            elif msg_type == 'flash_batch':
                status = data.get('status')
                
                if status == 'file_start':
                    current_file = data.get('file_num', 0)
                    current_file_name = data.get('file', 'unknown')
                    total = data.get('total', file_count)
                    print(f"\n[{current_file}/{total}] Flashing {current_file_name}...")
                
                elif status == 'progress':
                    pct = data.get('pct', 0)
                    sys.stdout.write(f"\r  Progress: {pct}%")
                    sys.stdout.flush()
                
                elif status == 'file_complete':
                    print(f"\r  ✓ {current_file_name} complete     ")
                
                elif status == 'complete':
                    print(f"\n✓ Batch flash complete ({data.get('time', '?')}s)")
                    if data.get('reset_performed'):
                        print("✓ Device reset")
                    return True, esptool_output if verbose else None
                
                elif status == 'error':
                    failed_file = data.get('file', 'unknown')
                    message = data.get('message', 'Unknown error')
                    print(f"\n✗ Flash failed on {failed_file}: {message}", file=sys.stderr)
                    return False, esptool_output if verbose else None
            
            # Handle unknown message types
            elif verbose:
                print(f"[UNKNOWN TYPE: {msg_type}] {data}")
                    
        except asyncio.TimeoutError:
            print(f"\n✗ Timeout waiting for flash response", file=sys.stderr)
            return False, esptool_output if verbose else None
    
    return True, esptool_output if verbose else None

async def do_flash_batch(files, baud=1500000, reset_after=True, bridge_uri=None, verbose=False):
    """Execute batch flash via WebSocket"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    async with websockets.connect(bridge_uri, ssl=ssl_context, ping_interval=None) as ws:
        print(f"Connected to bridge")
        print(f"Flashing {len(files)} files:")
        for f in files:
            print(f"  {f['filename']:40s} at {f['addr']} ({f.get('category', 'app')})")
        print(f"Baud rate: {baud}")
        if verbose:
            print(f"Verbose mode: ON (showing all WebSocket traffic)")
        print()
        
        return await flash_batch(ws, files, baud, reset_after, verbose)

def main():
    parser = argparse.ArgumentParser(description='Flash multiple binaries in one atomic operation')
    parser.add_argument('--project', '-p', required=True, help='Project directory')
    parser.add_argument('--target', '-t', help='Target chip (auto-detected if not specified)')
    parser.add_argument('--baud', '-b', type=int, help='Baud rate (auto-selected for target)')
    parser.add_argument('--no-reset', action='store_true', help='Skip device reset after flash')
    parser.add_argument('--files', '-f', nargs='+', metavar=('FILE', 'ADDR'), help='Manual file list')
    parser.add_argument('--skip-storage', action='store_true', help='Skip storage.bin')
    parser.add_argument('--dry-run', '-n', action='store_true', help='Show flash plan without flashing')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show all WebSocket traffic and esptool output')
    args = parser.parse_args()
    
    bridge_uri = get_bridge_uri()
    
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
            target = 'esp32s3'
            print(f"Using default target: {target}")
    
    baud = args.baud if args.baud else get_default_baud(target)
    
    files = []
    
    if args.files:
        if len(args.files) % 2 != 0:
            print("Error: --files requires pairs of (filename address)", file=sys.stderr)
            sys.exit(1)
        
        for i in range(0, len(args.files), 2):
            filename = args.files[i]
            addr = args.files[i + 1]
            category = 'app'
            if 'bootloader' in filename.lower():
                category = 'bootloader'
            elif 'partition' in filename.lower():
                category = 'partition'
            elif 'storage' in filename.lower():
                category = 'storage'
            
            files.append({'filename': filename, 'addr': addr, 'category': category})
    else:
        # Read files and addresses from ESP-IDF build artifacts
        files = get_flash_files_from_manifest(build_dir)
        storage = scan_for_storage(build_dir)
        if storage and not any(f.get('category') == 'storage' for f in files):
            files.append(storage)
    
    if args.skip_storage:
        files = [f for f in files if f.get('category') != 'storage']
    
    if not files:
        print("Error: No files to flash", file=sys.stderr)
        sys.exit(1)
    
    if args.dry_run:
        print(f"\n=== Flash Plan (dry run) ===")
        print(f"Target: {target}")
        print(f"Baud: {baud}")
        print(f"Reset after: {not args.no_reset}")
        print(f"\nFiles to flash ({len(files)}):")
        total_size = 0
        for i, f in enumerate(files, 1):
            filepath = build_dir / f['filename']
            if not filepath.exists():
                for subdir in ['bootloader', 'partition_table']:
                    alt_path = build_dir / subdir / f['filename']
                    if alt_path.exists():
                        filepath = alt_path
                        break
            size = filepath.stat().st_size if filepath.exists() else 0
            total_size += size
            print(f"  {i}. {f['filename']:40s} @ {f['addr']} ({size:,} bytes)")
        print(f"\n  Total: {total_size:,} bytes ({total_size / (1024*1024):.1f} MB)")
        print(f"\n✓ Dry run complete")
        return
    
    result = asyncio.run(do_flash_batch(files, baud=baud, reset_after=not args.no_reset, bridge_uri=bridge_uri, verbose=args.verbose))
    
    # Handle tuple return (success, output) or bool return
    if isinstance(result, tuple):
        success, esptool_output = result
    else:
        success = result
        esptool_output = None
    
    if success:
        print(f"\n✓ Flash batch complete!")
        print(f"Monitor with: esp-idf monitor")
    else:
        print(f"\n✗ Flash batch failed", file=sys.stderr)
        if esptool_output and args.verbose:
            print(f"\n--- Full esptool output ---")
            print(''.join(esptool_output))
            print(f"--- End esptool output ---")
        sys.exit(1)

if __name__ == '__main__':
    main()
