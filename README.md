🎛️ ESP32 Stream Deck Pro
A fully customizable Stream Deck built with ESP32, powered by a modern Python interface with drag & drop, profiles, macros, and custom icons.
Perfect for productivity, automation, media control, and everyday shortcuts.
---
🚀 Features
🎨 Clean and modern UI built with CustomTkinter
🧩 Fully customizable grid layout (rows & columns)
🖱️ Intuitive drag & drop system
🎯 Supports multiple action types:
Hotkeys
Media control
Open apps, folders, and URLs
🎭 Profile system for different setups
🎨 Full customization:
Button colors
Background
Grid borders
🔄 One-click ESP32 synchronization
🔌 Serial communication
💾 Auto-save configuration (`estado_programa.json`)
🧠 Command database support (`comandos.json`)
🖥️ Auto-start with Windows (optional)
📥 System tray support (optional)
---
🧱 Project Structure
```
📁 project/
├── interface.py          # Main Python interface
├── streamdeck.ino        # ESP32 firmware
├── comandos.json         # Command database
├── estado_programa.json  # Saved state (auto-generated)
├── 📁 icones/            # Button icons
```
---
⚙️ Requirements
Python
Python 3.10+
Dependencies
Install everything with:
```
pip install customtkinter pillow pyserial pyautogui pystray
```
---
🔌 ESP32 Setup
Install ESP32 support in Arduino IDE
Select the board:
```
esp32:esp32:esp32da
```
Upload:
```
streamdeck.ino
```
---
▶️ Getting Started
1. Launch the interface
```
python interface.py
```
---
2. Connect your ESP32
Go to the Console tab
Select your COM port
Click "Activate Deck"
---
3. Configure buttons
Drag icons into the grid
Assign actions:
Keys
Commands
URLs
Customize colors
---
4. Sync to device
Click:
```
🚀 SYNC DECK
```
---
🎮 Supported Actions
⌨️ Keyboard inputs (e.g. `f13`, `ctrl`, `volumeup`)
🔗 Open URLs
📂 Open folders
🖥️ Launch applications
🎵 Media control
🔙 Navigation (e.g. browser back)
---
🎨 Customization
Grid layout (rows × columns)
Screen orientation
Global colors
Custom icons
---
🧠 Profiles System
Create multiple profiles for different use cases:
🎮 Gaming
💻 Work
🎬 Streaming
Switch instantly from the interface.
---
⚠️ Notes
Some actions depend on your operating system
PyStray is optional (for system tray support)
Make sure to properly close the serial connection
---
💡 Roadmap / Future Ideas
Wi-Fi support (no serial required)
OBS integration
Multi-page support
Display feedback on device
Plugin system
---
📄 License
MIT — feel free to use and modify.
---
👨‍💻 Author
Developed by Ramiro Sanches
