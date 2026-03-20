#!/usr/bin/env python3
"""
esp-idf iterate - Full loop: Build + Upload + Flash + Monitor
"""

import subprocess
import sys
import argparse
import os
from pathlib import Path

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

def run_step(name, cmd):
    """Run a step and report"""
    print(f"\n{'='*50}")
    print(f"STEP: {name}")
    print('='*50)
    
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        print(f"\n✗ {name} failed", file=sys.stderr)
        return False
    
    print(f"✓ {name} complete")
    return True

def main():
    parser = argparse.ArgumentParser(description='Full iteration: Build + Upload + Flash + Monitor')
    parser.add_argument('--project', '-p', required=True, help='Project directory')
    parser.add_argument('--target', '-t', help='Target chip (esp32, esp32s3, esp32p4, etc.)')
    parser.add_argument('--clean', action='store_true', help='Clean build')
    parser.add_argument('--no-flash', action='store_true', help='Skip flash')
    parser.add_argument('--no-monitor', action='store_true', help='Skip monitor')
    parser.add_argument('--monitor-duration', type=int, default=5, help='Monitor duration in seconds')
    parser.add_argument('--idf-path', default=os.path.expanduser('~/esp-idf-v5.4'), help='ESP-IDF path')
    args = parser.parse_args()
    
    scripts_dir = Path(__file__).parent
    
    # Resolve project path for display
    project_path_resolved = resolve_project_path(args.project)
    
    # Target is required or auto-detected from build
    target = args.target
    
    print("="*50)
    print("ESP-IDF ITERATION")
    print("Design → Build → Upload → Flash → Verify")
    print(f"Project: {args.project}")
    print(f"Resolved: {project_path_resolved}")
    if target:
        print(f"Target: {target}")
    else:
        print("Target: auto-detect from build")
    print("="*50)
    
    # Step 1: Build
    build_cmd = [
        'python3', str(scripts_dir / 'build.py'),
        '--project', args.project,
        '--idf-path', args.idf_path
    ]
    
    if args.target:
        build_cmd.extend(['--target', args.target])
    
    if args.clean:
        build_cmd.append('--clean')
    
    if not run_step('BUILD', build_cmd):
        sys.exit(1)
    
    # Step 2: Upload
    upload_cmd = [
        'python3', str(scripts_dir / 'upload.py'),
        '--project', args.project
    ]
    
    if not run_step('UPLOAD', upload_cmd):
        sys.exit(1)
    
    # Step 3: Flash (batch - flashes all partitions including partition table)
    if not args.no_flash:
        flash_cmd = [
            'python3', str(scripts_dir / 'flash_batch.py'),
            '--project', args.project
        ]
        
        if args.target:
            flash_cmd.extend(['--target', args.target])
        
        # flash_batch handles all partitions atomically
        
        if not run_step('FLASH BATCH', flash_cmd):
            sys.exit(1)
    
    # Step 4: Monitor (no reset needed, device already booted from flash)
    if not args.no_monitor:
        monitor_cmd = [
            'python3', str(scripts_dir / 'monitor.py'),
            '--duration', str(args.monitor_duration)
        ]
        
        run_step('MONITOR', monitor_cmd)
    
    print("\n" + "="*50)
    print("✓ ITERATION COMPLETE")
    print("="*50)
    print()

if __name__ == '__main__':
    main()
