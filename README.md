# ESP-IDF Project Builder

A multi-target ESP32 development workflow tool supporting ESP32, ESP32-S2, ESP32-S3, ESP32-C3, ESP32-C6, and ESP32-P4.

## Key Features

- **Config-free operation**: Flash addresses read automatically from ESP-IDF build artifacts
- **Device discovery**: Query connected device type, MAC, and chip ID
- **Target verification**: Verify device matches build target before flashing
- **High-speed flashing**: 3Mbps default baud rate for faster uploads
- **Smart reconnection**: Bridge tracks devices by hardware ID across reconnects

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

### 3. Discover Connected Device

```bash
./esp-idf discover
```

### 4. Build and Flash

```bash
./esp-idf iterate --project ~/.openclaw/workspace/projects/esp-idf-projects/my-project --target esp32s3
```

## Commands

- `install` - Install ESP-IDF with multi-target support
- `new-project` - Create project from target-aware template
- `discover` - Show connected device info
- `build` - Compile for specified target
- `upload` - Upload binaries to bridge
- `flash` - Flash single binary
- `flash-batch` - Flash all partitions atomically
- `iterate` - Full workflow (build + upload + flash + monitor)
- `monitor` - Stream serial output

## Device Discovery

```bash
# Show connected device
./esp-idf discover

# Verify expected device
./esp-idf discover --compare esp32s3

# Flash with verification
./esp-idf flash --project ~/my-project --verify-target
```

## Target Support

| Target | Bootloader | Default Baud | Template |
|--------|------------|--------------|----------|
| ESP32 | 0x1000 | 3000000 | Generic |
| ESP32-S2 | 0x1000 | 3000000 | Generic |
| ESP32-S3 | 0x1000 | 3000000 | Canvas node |
| ESP32-C3 | 0x0000 | 3000000 | Generic |
| ESP32-C6 | 0x0000 | 3000000 | Generic |
| ESP32-P4 | 0x2000 | 3000000 | Display |

## Architecture

```
Container (VS Code) → Tailscale → Bridge (MacBook) → USB → ESP32
```

The bridge runs on a MacBook with USB access to ESP32 devices. It provides:
- WebSocket server for binary upload
- Smart device reconnection (30s timeout)
- ESP32-only port filtering
- Hardware ID tracking across reconnects

See `SKILL.md` for full documentation.

## License

Part of the Studio Alight collective.
