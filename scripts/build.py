#!/usr/bin/env python3
"""
esp-idf build - Compile ESP-IDF project for specified target

Generates version header with git commit info before building.
Configures chip revision compatibility for targets that need it.
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

def resolve_project_path(path_str):
    """Resolve project path - handle relative paths and tilde expansion"""
    path_str = os.path.expanduser(path_str)
    path = Path(path_str)
    
    if path.is_absolute():
        return path.resolve()
    
    if str(path).startswith('./'):
        return Path.cwd() / str(path)[2:]
    else:
        return Path.cwd() / path

def get_git_info(project_path):
    """Get git commit hash and date"""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=project_path, capture_output=True, text=True
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
            dirty_result = subprocess.run(
                ['git', 'diff', '--quiet'],
                cwd=project_path, capture_output=True
            )
            if dirty_result.returncode != 0:
                commit += '-dirty'
            return commit
    except Exception:
        pass
    return 'unknown'

def generate_version_header(project_path, project_name):
    """Generate version.h with build info"""
    git_commit = get_git_info(project_path)
    build_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    version_content = f'''/* Auto-generated version header */
#ifndef VERSION_H
#define VERSION_H

#define PROJECT_NAME "{project_name}"
#define GIT_COMMIT "{git_commit}"
#define BUILD_TIME "{build_time}"

#endif /* VERSION_H */
'''
    
    version_component = project_path / 'components' / 'version'
    version_component.mkdir(parents=True, exist_ok=True)
    (version_component / 'version.h').write_text(version_content)
    cmake_file = version_component / 'CMakeLists.txt'
    if not cmake_file.exists():
        cmake_file.write_text('idf_component_register(INCLUDE_DIRS ".")\n')
    
    return git_commit

def detect_target_from_sdkconfig(project_path):
    """Detect target from existing sdkconfig"""
    sdkconfig = project_path / 'sdkconfig'
    if sdkconfig.exists():
        content = sdkconfig.read_text()
        for line in content.split('\n'):
            if line.startswith('CONFIG_IDF_TARGET='):
                return line.split('=')[1].strip('"')
    return None

def configure_chip_revision(project_path, target):
    """Configure chip revision compatibility for targets that need it"""
    # Hardcoded chip revision configs for targets that need them
    revision_configs = {
        'esp32p4': """# Chip revision compatibility
CONFIG_ESP32P4_REV_MIN_0=y
CONFIG_ESP32P4_REV_MIN_FULL=0
"""
    }
    
    if not target or target not in revision_configs:
        return False
    
    sdkconfig_path = project_path / 'sdkconfig'
    if not sdkconfig_path.exists():
        return False
    
    content = sdkconfig_path.read_text()
    
    # Check if revision already configured
    revision_key = f'CONFIG_{target.upper()}_REV_MIN_'
    if revision_key in content:
        return False
    
    # Add target-specific revision config
    revision_config = revision_configs.get(target, '')
    if revision_config:
        with open(sdkconfig_path, 'a') as f:
            f.write('\n' + revision_config)
        print(f"  Configured chip revision for {target} compatibility")
        return True
    
    return False

def get_idf_path(args):
    """Get ESP-IDF path from args or environment"""
    if args.idf_path:
        return Path(args.idf_path).expanduser()
    
    # Check environment
    env_path = os.environ.get('IDF_PATH')
    if env_path:
        return Path(env_path)
    
    # Default location
    return Path.home() / f'esp-idf-v{args.idf_version}'

def main():
    parser = argparse.ArgumentParser(description='Build ESP-IDF project')
    parser.add_argument('--project', '-p', required=True, help='Project directory')
    parser.add_argument('--target', '-t', help='Target chip (esp32, esp32s3, esp32p4, etc.)')
    parser.add_argument('--clean', action='store_true', help='Clean build first')
    parser.add_argument('--idf-path', help='ESP-IDF path (default: ~/esp-idf-v5.4)')
    parser.add_argument('--idf-version', default='5.4', help='ESP-IDF version')
    args = parser.parse_args()
    
    # Resolve paths
    project_path = resolve_project_path(args.project)
    idf_path = get_idf_path(args)
    
    if not project_path.exists():
        print(f"Error: Project not found: {project_path}", file=sys.stderr)
        sys.exit(1)
    
    if not idf_path.exists():
        print(f"Error: ESP-IDF not found at {idf_path}", file=sys.stderr)
        print("Run: esp-idf install", file=sys.stderr)
        sys.exit(1)
    
    # Determine target
    target = args.target
    if not target:
        # Try to detect from existing sdkconfig
        target = detect_target_from_sdkconfig(project_path)
        if target:
            print(f"Detected target from sdkconfig: {target}")
        else:
            # Use sensible default
            target = 'esp32s3'
            print(f"Using default target: {target}")
    
    # Target info (hardcoded for known targets)
    target_info_map = {
        'esp32': {'name': 'ESP32', 'description': 'Original ESP32 (Xtensa LX6)'},
        'esp32s2': {'name': 'ESP32-S2', 'description': 'Single-core Xtensa LX7 with USB OTG'},
        'esp32s3': {'name': 'ESP32-S3', 'description': 'Dual-core Xtensa LX7 with AI/vector instructions'},
        'esp32c3': {'name': 'ESP32-C3', 'description': 'RISC-V single-core with Wi-Fi/BLE'},
        'esp32c6': {'name': 'ESP32-C6', 'description': 'RISC-V with Wi-Fi 6 and BLE 5'},
        'esp32p4': {'name': 'ESP32-P4', 'description': 'High-performance RISC-V with LCD interface'},
    }
    
    if target in target_info_map:
        info = target_info_map[target]
        print(f"Target: {info['name']}")
        print(f"  {info['description']}")
    else:
        print(f"Target: {target}")
    
    # Extract project name
    project_name = "project"
    cmake_file = project_path / 'CMakeLists.txt'
    if cmake_file.exists():
        content = cmake_file.read_text()
        import re
        match = re.search(r'project\s*\(\s*([\w-]+)', content)
        if match:
            project_name = match.group(1)
    
    # Generate version header
    print(f"\nProject: {project_name}")
    git_commit = generate_version_header(project_path, project_name)
    print(f"Git commit: {git_commit}")
    
    # Run set-target if needed
    sdkconfig = project_path / 'sdkconfig'
    target_set = False
    
    if not sdkconfig.exists():
        print(f"\nSetting target: {target}")
        result = subprocess.run(
            f'source {idf_path}/export.sh && cd {project_path} && idf.py set-target {target}',
            shell=True, executable='/bin/bash'
        )
        if result.returncode != 0:
            print("✗ set-target failed", file=sys.stderr)
            sys.exit(1)
        target_set = True
    else:
        # Check if target matches
        with open(sdkconfig) as f:
            sdkconfig_content = f.read()
            expected = f'CONFIG_IDF_TARGET="{target}"'
            if expected not in sdkconfig_content:
                print(f"\nTarget mismatch. Reconfiguring for: {target}")
                result = subprocess.run(
                    f'source {idf_path}/export.sh && cd {project_path} && idf.py set-target {target}',
                    shell=True, executable='/bin/bash'
                )
                if result.returncode != 0:
                    print("✗ set-target failed", file=sys.stderr)
                    sys.exit(1)
                target_set = True
    
    # Configure chip revision if needed
    if target_set or sdkconfig.exists():
        configure_chip_revision(project_path, target)
    
    # Clean if requested
    if args.clean:
        print("\nClean build requested")
        subprocess.run(
            f'source {idf_path}/export.sh && cd {project_path} && rm -rf build',
            shell=True, executable='/bin/bash'
        )
    
    # Build
    print(f"\nBuilding: {project_path}")
    print(f"Target: {target}")
    result = subprocess.run(
        f'source {idf_path}/export.sh && cd {project_path} && idf.py build',
        shell=True, executable='/bin/bash'
    )
    
    if result.returncode == 0:
        print("\n✓ Build successful!")
        build_dir = project_path / 'build'
        expected_app = build_dir / f"{project_name}.bin"
        
        if expected_app.exists():
            size = expected_app.stat().st_size
            print(f"  build/{expected_app.name}: {size:,} bytes")
            
            if git_commit != 'unknown':
                versioned_name = f"{project_name}-{git_commit}.bin"
                versioned_path = build_dir / versioned_name
                if not versioned_path.exists():
                    import shutil
                    shutil.copy2(expected_app, versioned_path)
                    print(f"  {versioned_name}: {size:,} bytes (versioned)")
            
            print(f"\nReady: esp-idf upload --project {args.project}")
    else:
        print("\n✗ Build failed", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
