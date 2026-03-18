# ESP-IDF Project Builder

Build, upload, and flash ESP-IDF projects across multiple ESP32 targets (ESP32, ESP32-S2, ESP32-S3, ESP32-C3, ESP32-C6, ESP32-P4).

## Overview

This skill provides a container-to-hardware workflow for ESP32 development:

```
┌─────────────┐     Tailscale      ┌──────────┐     USB      ┌─────────┐
│  Container  │ ◄────────────────► │  Bridge  │ ◄──────────► │  ESP32  │
│  (VS Code)  │    (WireGuard)     │  (Mac)   │   Serial   │  Target │
└─────────────┘                    └──────────┘            └─────────┘
```

The bridge (MacBook) runs a WebSocket server that receives binaries from the container and flashes them to the ESP32 via esptool.

## Key Features

- **Config-free operation**: Flash addresses read automatically from ESP-IDF build artifacts
- **Device discovery**: Query connected device type, MAC, and chip ID
- **Target verification**: Verify device matches build target before flashing
- **High-speed flashing**: 3Mbps default baud rate for faster uploads
- **Smart reconnection**: Bridge tracks devices by hardware ID across reconnects
- **Multi-target support**: ESP32, ESP32-S2, ESP32-S3, ESP32-C3, ESP32-C6, ESP32-P4

## Installation

```bash
cd ~/.openclaw/workspace/skills/esp-idf-project-builder
./esp-idf install --targets esp32s3,esp32p4
```

This installs ESP-IDF v5.4 with support for the specified targets.

## Commands

### `install` — Install ESP-IDF
```bash
./esp-idf install --targets esp32s3,esp32p4
```
Options:
- `--targets` — Comma-separated list of targets (default: esp32,esp32s3)

### `new-project` — Create from Template
```bash
./esp-idf new-project --name my-project --target esp32s3
```
Options:
- `--name` — Project name
- `--target` — Target chip (esp32, esp32s2, esp32s3, esp32c3, esp32c6, esp32p4)
- `--template` — Template name (esp32p4-display, esp32s3-canvas, esp32-generic)
- `--output` — Output directory (default: ~/.openclaw/workspace/projects/esp-idf-projects/)

### `discover` — Discover Connected Device
```bash
./esp-idf discover                    # Show connected device
./esp-idf discover --compare esp32s3  # Verify expected device
```
Shows:
- Bridge version and connection status
- Device target (esp32s3, esp32c6, etc.)
- MAC address
- Chip ID (or MAC for devices without chip ID)

Exit codes:
- `0` — Device found (and matches if `--compare` used)
- `1` — No device detected
- `2` — Device mismatch (with `--compare`)

### `build` — Compile Project
```bash
./esp-idf build --project ~/my-project --target esp32s3
```
Options:
- `--project` — Path to project directory
- `--target` — Target chip
- `--clean` — Clean build (rm -rf build/ before building)

Build generates:
- `build/flash_args` — Flash arguments for esptool (read at runtime)
- `build/*.bin` — Binary partitions
- `build/project.elf` — ELF file for debugging

### `upload` — Upload to Bridge
```bash
./esp-idf upload --project ~/my-project
```
Uploads all binaries from `build/` to the bridge's staging area.

### `flash` — Flash Single Binary
```bash
./esp-idf flash --project ~/my-project --file build/my-project.bin --addr 0x10000
```
Options:
- `--project` — Project path (for context)
- `--file` — Binary file to flash
- `--addr` — Flash address
- `--target` — Target chip (for baud rate)
- `--verify-target` — Verify connected device matches build target
- `--chip-id` — Query chip ID without flashing
- `--verbose` — Show all WebSocket traffic

### `flash-batch` — Flash All Partitions
```bash
./esp-idf flash-batch --project ~/my-project --target esp32s3
```
Reads `build/flash_args` and flashes all partitions atomically.

Options:
- `--project` — Project directory
- `--target` — Target chip
- `--baud` — Baud rate (default: 3000000)
- `--dry-run` — Show flash plan without flashing
- `--verbose` — Show all WebSocket traffic

### `monitor` — Serial Output
```bash
./esp-idf monitor --duration 30
```
Streams serial output from the ESP32 via the bridge.

Options:
- `--duration` — Monitor duration in seconds (default: 15)

### `iterate` — Full Workflow
```bash
./esp-idf iterate --project ~/my-project --target esp32s3 --clean
```
Runs: build → upload → flash-batch → monitor

Options:
- `--project` — Project directory
- `--target` — Target chip
- `--clean` — Clean build first
- `--no-flash` — Skip flash step
- `--no-monitor` — Skip monitor step
- `--monitor-duration` — Monitor duration in seconds

## Target Configuration

| Target | Bootloader | Default Baud | Key Features |
|--------|------------|--------------|--------------|
| ESP32 | 0x1000 | 3000000 | WiFi, BT, Classic BT |
| ESP32-S2 | 0x1000 | 3000000 | WiFi, USB OTG |
| ESP32-S3 | 0x1000 | 3000000 | WiFi, BT, USB OTG, LCD/CAM |
| ESP32-C3 | 0x0000 | 3000000 | WiFi, BT (RISC-V) |
| ESP32-C6 | 0x0000 | 3000000 | WiFi 6, BT, Zigbee (RISC-V) |
| ESP32-P4 | 0x2000 | 3000000 | WiFi 6, BT, MIPI DSI, LCD/CAM (RISC-V) |

## Device Discovery and Verification

### Check Connected Device
```bash
./esp-idf discover
```
Output:
```
Bridge:     v2.0-localip (abc1234)
Connected:  True
Port:       /dev/cu.usbmodem2101

Device Info:
  Target:   esp32s3
  MAC:      80:b5:4e:f3:2d:04
  Chip ID:  80:b5:4e:f3:2d:04
  Status:   connected
```

### Verify Before Flashing
```bash
./esp-idf flash --project ~/my-project --verify-target
```
If device doesn't match:
```
⚠ Target mismatch!
  Build target: esp32s3
  Connected:    esp32c6

Use --target to override or connect the correct device.
```

### Compare Expected Device
```bash
./esp-idf discover --compare esp32s3 && ./esp-idf build --project ~/my-project
```

## Bridge Setup

The bridge runs on a MacBook with USB access to ESP32 devices:

1. **Install bridge dependencies:**
   ```bash
   pip3 install websockets pyserial
   ```

2. **Run the bridge server:**
   ```bash
   python3 esp32-bridge.py --auto
   ```

3. **Verify Tailscale connectivity:**
   ```bash
   ping esp32-bridge.tailbdd5a.ts.net
   ```

## Bridge Features

### Smart Reconnection
- Tracks devices by USB hardware ID (VID:PID:Serial)
- Waits 30s for same device to reconnect
- After timeout, accepts any ESP32 device
- Excludes non-ESP32 ports (debug consoles, Bluetooth, etc.)

### Device Detection
- Auto-detects chip type (ESP32-S3, ESP32-C6, etc.)
- Returns MAC address for devices without chip ID
- Handles EUI-64 format MACs (ESP32-C6)

## Project Structure

```
my-project/
├── CMakeLists.txt          # Project CMake file
├── sdkconfig               # SDK configuration
├── sdkconfig.defaults      # Default config for target
├── main/
│   ├── CMakeLists.txt
│   └── main.c             # Application entry point
├── components/              # Custom components (optional)
└── build/                 # Build output (generated)
    ├── flash_args          # Flash arguments (read at runtime)
    ├── bootloader.bin      # Bootloader
    ├── partition-table.bin # Partition table
    └── my-project.bin      # Application binary
```

## Version Header Generation

Build automatically generates `main/version.h` with git commit info:

```c
#define PROJECT_VERSION "v1.0.0-abc123-dirty"
#define PROJECT_COMMIT "abc123"
#define PROJECT_DATE "2026-03-16T14:30:00"
```

Include in your code:
```c
#include "version.h"
ESP_LOGI(TAG, "Version: %s", PROJECT_VERSION);
```

## Chip Revision Compatibility

For ESP32-P4 early samples (v1.0), the build automatically applies revision compatibility settings via `sdkconfig.defaults`.

## Troubleshooting

### Build fails with "Target not set"
Run: `idf.py set-target esp32s3` (or your target)

### Upload fails with connection error
- Verify bridge is running: `curl http://esp32-bridge.tailbdd5a.ts.net:5679/status`
- Check Tailscale: `tailscale status`

### Flash fails with "Failed to connect"
- Check USB cable (must be data cable, not charge-only)
- Hold BOOT button while resetting ESP32
- Verify correct baud rate for target

### Monitor shows garbled output
- Verify correct baud rate (3Mbps default)
- Check serial port selection on bridge

### Device not detected
- Run `./esp-idf discover` to check connection
- Verify device is ESP32 (not other USB device)
- Check bridge logs for "No ESP32 device found"

## Environment Variables

- `ESP_BRIDGE_HOST` — Bridge hostname (default: esp32-bridge.tailbdd5a.ts.net)
- `ESP_BRIDGE_PORT` — WebSocket port (default: 5678)
- `ESP_BRIDGE_HTTP_PORT` — HTTP port (default: 5679)

## Dependencies

- Python 3.10+
- ESP-IDF v5.4
- PyYAML (`pip3 install pyyaml`)
- WebSocket client (included)

## License

Part of the Studio Alight collective.
