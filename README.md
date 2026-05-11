# 🎛️ ESP32 Stream Deck Pro

A fully customizable **Stream Deck built with ESP32**, powered by a modern Python interface with **drag & drop, profiles, macros, and custom icons**.

Perfect for productivity, automation, media control, and everyday shortcuts.

---

## 🚀 Features

- 🎨 Clean and modern UI built with **CustomTkinter**
- 🧩 Customizable **grid layout (rows & columns)**
- 🖱️ **drag & drop system** (Work in progress)
- 🎯 Supports multiple action types:
  - Hotkeys
  - Media control
  - Open apps, folders, and URLs
- 🎭 **Profile system** for different setups
- 🎨 Customization:
  - Button colors
  - Background color
  - Grid borders
- 🔄 One-click **ESP32 synchronization**
- 🔌 Serial communication
- 💾 Auto-save configuration (`estado_programa.json`)
- 🧠 Command database support (`comandos.json`)
- 🖥️ Auto-start with Windows (optional)
- 📥 System tray support (optional)

---

## 🧱 Project Structure

```
📁 project/
├── interface.py          # Main Python interface
├── streamdeck.ino        # ESP32 firmware
├── comandos.json         # Command database
├── estado_programa.json  # Saved state (auto-generated)
├── 📁 icones/            # Button icons
```

---

## ⚙️ Requirements

### Python

- Python 3.10+

### Dependencies

Install everything with:

```
pip install customtkinter pillow pyserial pyautogui pystray
```

---

## 🔌 ESP32 Setup

1. Install ESP32 support in Arduino IDE  
2. Select the board:

```
esp32:esp32:esp32da
```

3. Upload:

```
streamdeck.ino
```

---

## ▶️ Getting Started

### 1. Launch the interface

```
python interface.py
```

---

### 2. Connect your ESP32

- Go to the **Console tab**
- Select your COM port
- Click **"Activate Deck"**

---

### 3. Configure buttons

- Drag icons into the grid
- Assign actions:
  - Keys
  - Commands
  - URLs
- Customize colors

---

### 4. Sync to device

Click:

```
🚀 SYNC DECK
```

---

## 🎮 Supported Actions

- ⌨️ Keyboard inputs (e.g. `f13`, `ctrl`, `volumeup`) (HOTKEYS NOT WORKING YET)
- 🔗 Open URLs
- 📂 Open folders
- 🖥️ Launch applications
- 🎵 Media control
- 🔙 Navigation (e.g. browser back)

---

## 🎨 Customization

- Grid layout (rows × columns)
- Screen orientation
- Global colors
- Custom icons

---

## 🧠 Profiles System

Create multiple profiles for different use cases:

- 🎮 Gaming
- 💻 Work
- 🎬 Streaming

Switch by uploading to the CYD

---

## ⚠️ Notes

- This project is a work in progress
- Make sure to properly close the serial connection

---

## 💡 Roadmap / Future Ideas

- OBS integration
- Multi-page support
- Built-in Soundpad

---

## 📄 License

MIT — feel free to use and modify.

---

## 👨‍💻 Author

Developed by **Ramiro Sanches**
