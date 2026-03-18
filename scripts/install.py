#!/usr/bin/env python3
"""
esp-idf install - Install ESP-IDF with multi-target support

Sets up ESP-IDF and installs tools for specified targets.
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path

ESP_IDF_VERSION = "5.4"
DEFAULT_TARGETS = "esp32,esp32s2,esp32s3,esp32c3,esp32c6,esp32p4"

def run_command(cmd, cwd=None, shell=False, check=True):
    """Run shell command with output streaming"""
    print(f"  $ {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        shell=shell,
        check=check,
        capture_output=False,
        text=True
    )
    return result

def main():
    parser = argparse.ArgumentParser(
        description='Install ESP-IDF with multi-target support'
    )
    parser.add_argument(
        '--targets', '-t',
        default=DEFAULT_TARGETS,
        help=f'Comma-separated list of targets (default: {DEFAULT_TARGETS})'
    )
    parser.add_argument(
        '--version', '-v',
        default=ESP_IDF_VERSION,
        help=f'ESP-IDF version (default: {ESP_IDF_VERSION})'
    )
    parser.add_argument(
        '--path', '-p',
        default=f'~/esp-idf-v{ESP_IDF_VERSION}',
        help=f'Installation path (default: ~/esp-idf-v{ESP_IDF_VERSION})'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Reinstall if already exists'
    )
    args = parser.parse_args()
    
    idf_path = Path(args.path).expanduser().resolve()
    targets = args.targets.replace(' ', '')
    
    print("="*60)
    print("ESP-IDF Installation")
    print("="*60)
    print(f"Version:  {args.version}")
    print(f"Path:     {idf_path}")
    print(f"Targets:  {targets}")
    print()
    
    # Check if already installed
    if idf_path.exists() and not args.force:
        print(f"ESP-IDF already exists at {idf_path}")
        print("Use --force to reinstall")
        print()
        print("To activate existing installation:")
        print(f"  source {idf_path}/export.sh")
        return
    
    # Remove existing if force
    if idf_path.exists() and args.force:
        print(f"Removing existing installation...")
        import shutil
        shutil.rmtree(idf_path)
    
    # Clone ESP-IDF
    print("\n[1/3] Cloning ESP-IDF...")
    clone_cmd = [
        'git', 'clone',
        '-b', f'v{args.version}',
        '--recursive',
        'https://github.com/espressif/esp-idf.git',
        str(idf_path)
    ]
    
    try:
        run_command(clone_cmd)
    except subprocess.CalledProcessError as e:
        print(f"✗ Clone failed: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Install tools
    print("\n[2/3] Installing tools for targets...")
    install_script = idf_path / 'install.sh'
    if not install_script.exists():
        print(f"✗ install.sh not found at {install_script}", file=sys.stderr)
        sys.exit(1)
    
    try:
        run_command([str(install_script), targets], cwd=idf_path)
    except subprocess.CalledProcessError as e:
        print(f"✗ Tool installation failed: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Create convenience scripts
    print("\n[3/3] Creating convenience scripts...")
    
    # Activation script
    activate_script = Path.home() / '.esp_idf_activate'
    activate_content = f'''#!/bin/bash
# ESP-IDF activation script
export IDF_PATH="{idf_path}"
. "$IDF_PATH/export.sh"
'''
    activate_script.write_text(activate_content)
    activate_script.chmod(0o755)
    
    # Shell alias helper
    alias_script = Path.home() / '.esp_idf_aliases'
    alias_content = f'''# ESP-IDF aliases
alias get_idf='. {idf_path}/export.sh'
alias idf='idf.py'
'''
    alias_script.write_text(alias_content)
    
    print("\n" + "="*60)
    print("✓ ESP-IDF installation complete!")
    print("="*60)
    print()
    print("Quick start:")
    print(f"  source {idf_path}/export.sh")
    print("  idf.py --version")
    print()
    print("Or use the activation script:")
    print(f"  source ~/.esp_idf_activate")
    print()
    print("To add aliases to your shell:")
    print(f"  echo 'source ~/.esp_idf_aliases' >> ~/.bashrc")
    print()
    print("Create a new project:")
    print("  esp-idf new-project --name my-project --target esp32s3")
    print()
    print("Targets installed:")
    for target in targets.split(','):
        print(f"  ✓ {target}")

if __name__ == '__main__':
    main()
