# KeyPrism

**Your keyboard. Your colors. Your rhythm.**

![Platform](https://img.shields.io/badge/Platform-Windows-blue)
![Language](https://img.shields.io/badge/Language-Python-yellow)
![Hardware](https://img.shields.io/badge/Hardware-Acer%20Aspire%207-green)

KeyPrism is a lightweight RGB keyboard lighting controller designed for the Acer Aspire 7. It aims to bring dynamic lighting effects to compatible laptop keyboards through the existing vendor lighting interface, without requiring custom firmware or BIOS modifications.

## Features

The project focuses on four lighting modes:

| Effect | Description |
| --- | --- |
| Rainbow | Smooth, full-keyboard transitions through the color spectrum. |
| Breathing | Gradual fade-in and fade-out lighting. |
| Music Sync | Lighting that reacts to audio activity. |
| Reactive Typing | Full-keyboard flashes in response to keystrokes. |

## Hardware compatibility

| Component | Target |
| --- | --- |
| Laptop | Acer Aspire 7 A715-79G |
| Operating system | Windows |
| Runtime | Python 3.11 (64-bit) |
| Lighting interface | Acer/Insyde vendor interface (`InsydeDCHU.dll`) |

Other Acer models may use different lighting controllers and are not guaranteed to work.

## How it works

KeyPrism generates RGB color values for lighting effects and sends them to the keyboard through the compatible vendor lighting interface. This approach avoids direct BIOS or embedded-controller modifications.

## Getting started

Clone the repository:

```bash
git clone https://github.com/hannsraaz/keyprism.git
cd keyprism
```

Use a compatible Windows laptop with its original vendor lighting drivers installed. Follow the setup and launch instructions provided with the source code.

## Limitations

- Per-key RGB effects are not supported by the target lighting interface.
- Reactive typing is intended to affect the full keyboard rather than individual keys.
- Brightness can be simulated by scaling RGB values where native brightness control is unavailable.
- Compatibility outside the target laptop model has not been established.

## Contributing

Bug reports, compatibility feedback, performance improvements, and new lighting effect ideas are welcome. When reporting hardware issues, include your laptop model and Windows version.

## Disclaimer

KeyPrism is an independent project and is not affiliated with Acer, Insyde Software, or OpenRGB. Use only on compatible hardware. Vendor drivers and libraries remain subject to their respective licenses.

## License

See the repository's LICENSE file, if provided, for applicable terms.

---

Built for laptop enthusiasts who want more control over their RGB lighting.
