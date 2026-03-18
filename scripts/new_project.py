#!/usr/bin/env python3
"""
esp-idf new-project - Create project from template

Target-aware template selection for ESP32 family.
"""

import argparse
import subprocess
import sys
import os
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

def get_template_for_target(target, chip_config):
    """Get template repo for target"""
    templates = chip_config.get('templates', {})
    
    # Map target to template
    template_map = {
        'esp32p4': 'esp32p4-display',
        'esp32s3': 'esp32s3-canvas',
        'esp32': 'esp32-generic',
        'esp32s2': 'esp32-generic',
        'esp32c3': 'esp32-generic',
        'esp32c6': 'esp32-generic'
    }
    
    template_key = template_map.get(target, 'esp32-generic')
    template = templates.get(template_key, {})
    
    return template.get('repo', 'https://github.com/espressif/esp-idf-template.git')

def main():
    parser = argparse.ArgumentParser(description='Create new ESP-IDF project from template')
    parser.add_argument('--name', '-n', required=True, help='Project name')
    parser.add_argument('--target', '-t', default='esp32s3', 
                       help='Target chip (esp32, esp32s3, esp32p4, etc.)')
    parser.add_argument('--workspace', '-w', 
                       default=os.path.expanduser('~/.openclaw/workspace/projects/esp-idf-projects'),
                       help='Parent directory for projects')
    parser.add_argument('--template', help='Custom template URL (overrides target selection)')
    parser.add_argument('--keep-name', action='store_true',
                       help='Keep original template project name')
    args = parser.parse_args()
    
    chip_config = load_chip_config()
    
    # Sanitize project name
    project_name = args.name.replace(' ', '-').replace('_', '-')
    
    # Resolve workspace path
    workspace_arg = Path(args.workspace)
    if not workspace_arg.is_absolute():
        if str(workspace_arg).startswith('./'):
            workspace = Path.cwd() / str(workspace_arg)[2:]
        else:
            workspace = Path.cwd() / workspace_arg
    else:
        workspace = workspace_arg.expanduser().resolve()
    
    project_path = workspace / project_name
    
    if project_path.exists():
        print(f"Error: Directory already exists: {project_path}", file=sys.stderr)
        sys.exit(1)
    
    # Get template URL
    if args.template:
        template_repo = args.template
        template_name = "custom"
    else:
        template_repo = get_template_for_target(args.target, chip_config)
        template_name = args.target
    
    print(f"Creating new project: {project_name}")
    print(f"Location: {project_path}")
    print(f"Target: {args.target}")
    print(f"Template: {template_repo}")
    print()
    
    # Create workspace
    workspace.mkdir(parents=True, exist_ok=True)
    
    # Clone template
    print("→ Cloning template...")
    result = subprocess.run(
        ['git', 'clone', template_repo, str(project_path)],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        print(f"Error: Clone failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    
    # Remove .git to detach from template
    git_dir = project_path / '.git'
    if git_dir.exists():
        import shutil
        shutil.rmtree(git_dir)
    
    # Rename project in CMakeLists.txt
    cmake_file = project_path / 'CMakeLists.txt'
    if cmake_file.exists() and not args.keep_name:
        print(f"→ Updating CMakeLists.txt: project({project_name})...")
        content = cmake_file.read_text()
        # Try to find and replace project name
        content = re.sub(r'project\s*\(\s*\w+\s*\)', f'project({project_name})', content)
        cmake_file.write_text(content)
    
    # Initialize fresh git repo
    print("→ Initializing git repository...")
    subprocess.run(['git', 'init'], cwd=project_path, capture_output=True)
    subprocess.run(['git', 'add', '.'], cwd=project_path, capture_output=True)
    subprocess.run(['git', 'commit', '-m', f'Initial commit: {project_name}'], 
                   cwd=project_path, capture_output=True)
    
    # Success
    print("\n✓ Project created successfully!")
    print()
    print(f"Next steps:")
    print(f"  cd {project_path}")
    print(f"  source ~/esp-idf-v5.4/export.sh")
    print(f"  idf.py set-target {args.target}")
    print(f"  idf.py build")
    print()
    print(f"Or use the skill:")
    print(f"  esp-idf build --project {project_path} --target {args.target}")
    print(f"  esp-idf iterate --project {project_path} --target {args.target}")

if __name__ == '__main__':
    main()
