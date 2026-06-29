# 🐾 Zoomies

> **A four-key rhythm game inspired by classic arcade dance games.**
>
> Built with ❤️ by **PixelPaws Studio**.

---

## 🎮 Features

* 🎵 **Core Rhythm Action**: Fast-paced 4-key scrolling note gameplay with precise timing feedback.
* ⚡ **Versus & Co-Op Multiplayer**: Play side-by-side with a friend in standard Co-Op, Versus, or FNF-style struggle modes.
* 👥 **Local Player Profiles**: Custom names, choose your starting retro avatar, track total play stats, achievements, and view top 10 best-score cards.
* 🎨 **Theme Modding System**: Make the game yours! Fully customizable visual themes with custom background images, vector or custom `.png` arrow textures, and color schemes via `theme.json`.
* 🕹️ **Dance Pad & Controller Mapping**: Plug-and-play support for L-Tek and standard USB dance pads with fully customizable button mapping in Settings.
* 📝 **Chart Editor**: Compose, edit, and test your own charts directly in the built-in chart editor.
* 📂 **StepMania Support**: Automatically loads standard StepMania (`.sm`) songs and custom charts.

---

## 🚀 Getting Started

### Download & Play

Download the latest standalone Windows executable (`Zoomies.exe`) from the **Releases** page or compile from source.

### Run from Source

```bash
git clone https://github.com/janet-phan/zoomies.git
cd zoomies
pip install -r requirements.txt
python main.py
```

---

## 🎨 Theme Modding Guide

Zoomies features an easy-to-use theme modding system! Create a directory inside the `themes/` folder of your game installation (e.g. `themes/CyberNeon/`) and place a `theme.json` inside it.

### `theme.json` Schema Schema
```json
{
    "name": "CyberNeon",
    "bg_color": [10, 5, 20],
    "text_color": [240, 240, 250],
    "accent_color": [0, 255, 204],
    "lane_colors": [
        [255, 0, 128],
        [0, 191, 255],
        [50, 205, 50],
        [255, 165, 0],
        [255, 215, 0]
    ],
    "bg_image": "background.png",
    "arrow_images": {
        "left": "arrow_left.png",
        "down": "arrow_down.png",
        "up": "arrow_up.png",
        "right": "arrow_right.png"
    }
}
```
*Custom background and arrow images should be placed in the same custom theme folder.*

---

## 🕹️ Connecting an L-Tek Dance Pad
1. Connect the L-Tek pad via USB.
2. Open **SETTINGS** in the main menu.
3. Change **P1 DEVICE** from `Keyboard` to `Gamepad`.
4. Select **REMAP P1 GAMEPAD** and step on your pad panels to map Left, Down, Up, and Right.
5. Save and start dancing!

---

## 🗂 Project Structure

```
zoomies/
├── characters/     # Bobbing dancer visual frames
├── songs/          # Folder for .sm songs, music, and charts
├── themes/         # Mod theme directories
├── gameplay.py     # Gameplay loops, notes scrolling, and timing
├── editor.py       # Built-in chart composer
├── sm_parser.py    # StepMania chart importer
├── input_manager.py# Keyboard & controller remapper
├── theme_manager.py# Theme loader and renderer
└── main.py         # App entrypoint and menu flows
```

---

## ❤️ Why "Zoomies"?

Anyone who's lived with a cat (or dog) knows the feeling.

One moment they're peacefully sleeping... The next...

**Maximum speed. Maximum chaos.**

That same burst of energy inspired the fast-paced rhythm gameplay of **Zoomies**.

---

## 🤝 Contributing

Bug reports, feature requests, and pull requests are always welcome!
If you'd like to contribute charts, themes, bug fixes, or ideas, feel free to open a Pull Request.

---

## 📜 License

This project is licensed under the **GNU General Public License v3 (GPL v3)**. See the `LICENSE` file for details.

*Note: The GPL v3 License applies to the source code only. The PixelPaws Studio and Zoomies names, logos, artwork, music, and other branding assets are © Janet Phan and are not covered under the GPL v3 unless explicitly stated.*

---

🐾 **PixelPaws Studio**

*Small games. Big ideas. Built one pixel at a time.*
