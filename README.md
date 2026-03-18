# ESP-IDF Project Builder

A multi-target ESP32 development workflow tool supporting ESP32, ESP32-S2, ESP32-S3, ESP32-C3, ESP32-C6, and ESP32-P4.

## Installation

```bash
cd ~/.openclaw/workspace/skills
git clone https://github.com/studioalight/esp-idf-project-builder.git
```

## Quick Start

### 1. Install ESP-IDF

```bash
cd ~/.openclaw/workspace/skills/esp-idf-project-builder
./esp-idf install --targets esp32s3,esp32p4
```

### 2. Create a Project

```bash
./esp-idf new-project --name my-project --target esp32s3
```

### 3. Build and Flash

```bash
./esp-idf iterate --project ~/.openclaw/workspace/projects/esp-idf-projects/my-project --target esp32s3
```

## Commands

- `install` - Install ESP-IDF with multi-target support
- `new-project` - Create project from target-aware template
- `build` - Compile for specified target
- `upload` - Upload binaries to bridge
- `flash` - Flash single binary
- `flash-batch` - Flash all partitions atomically
- `iterate` - Full workflow (build + upload + flash + monitor)
- `monitor` - Stream serial output

## Target Support

| Target | Bootloader | Default Baud | Template |
|--------|------------|--------------|----------|
| ESP32 | 0x1000 | 921600 | Generic |
| ESP32-S2 | 0x1000 | 921600 | Generic |
| ESP32-S3 | 0x1000 | 921600 | Canvas node |
| ESP32-C3 | 0x0000 | 460800 | Generic |
| ESP32-C6 | 0x0000 | 460800 | Generic |
| ESP32-P4 | 0x2000 | 3000000 | Display |

## Architecture

```
Container (VS Code) → Tailscale → Bridge (MacBook) → USB → ESP32
```

See `SKILL.md` for full documentation.

## License

Part of the Studio Alight collective.
