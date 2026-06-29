import pygame
import math
import random
import os
import json
from config import settings, BASE_DIR

class ThemeManager:
    # Color Palettes
    COLOR_BG_RETRO = (15, 10, 25)       # Deep synthwave purple-black
    COLOR_BG_MINIMAL = (245, 245, 247)  # Light Apple-like gray

    # Retro neon colors
    RETRO_LANE_COLORS = [
        (255, 0, 128),   # Neon Pink
        (0, 191, 255),   # Neon Blue
        (50, 205, 50),   # Neon Green
        (255, 165, 0),   # Neon Orange
        (255, 215, 0)    # Gold (5th lane)
    ]
    
    # Minimalist colors
    MINIMAL_LANE_COLORS = [
        (80, 90, 100),
        (80, 90, 100),
        (80, 90, 100),
        (80, 90, 100),
        (80, 90, 100)
    ]

    # Guitar Hero colors
    HERO_LANE_COLORS = [
        (0, 200, 0),     # Green
        (220, 0, 0),     # Red
        (230, 230, 0),   # Yellow
        (0, 120, 255),   # Blue
        (255, 120, 0)    # Orange
    ]

    # Retro Pixel colors
    RETRO_PIXEL_COLORS = [
        (255, 45, 45),   # Red
        (45, 255, 45),   # Green
        (45, 45, 255),   # Blue
        (255, 255, 45),  # Yellow
        (255, 45, 255)   # Magenta
    ]

    # Futuristic Cyberpunk colors
    FUTURISTIC_COLORS = [
        (0, 255, 204),   # Cyan
        (255, 0, 128),   # Hot Pink
        (180, 0, 255),   # Neon Purple
        (0, 128, 255),   # Electric Blue
        (255, 215, 0)    # Gold
    ]

    # Kawaii Pink pastel colors
    KAWAII_PINK_COLORS = [
        (255, 140, 170), # Pastel Red/Pink
        (255, 170, 195), # Soft Coral Pink
        (255, 200, 220), # Light Lavender Pink
        (255, 160, 200), # Orchid Pink
        (255, 190, 210)  # Rose Pink
    ]

    # Neko Pixel cute colors
    NEKO_PIXEL_COLORS = [
        (186, 85, 211),  # Medium Orchid
        (255, 105, 180), # Hot Pink
        (255, 182, 193), # Light Pink
        (255, 222, 173), # Navajo White (Yellowish)
        (238, 130, 238)  # Violet
    ]

    def __init__(self):
        # Base arrow points pointing UP (2) centered at (0, 0)
        self.base_arrow_points = [
            (0, -28),
            (24, -4),
            (10, -4),
            (10, 28),
            (-10, 28),
            (-10, -4),
            (-24, -4)
        ]
        self.themes_dir = os.path.join(BASE_DIR, "themes")
        self.custom_themes = {}
        self.custom_theme_assets = {}
        
        self.setup_and_scan_custom_themes()

    def setup_and_scan_custom_themes(self):
        if not os.path.exists(self.themes_dir):
            os.makedirs(self.themes_dir)
            
        readme_path = os.path.join(self.themes_dir, "readme.txt")
        if not os.path.exists(readme_path):
            try:
                with open(readme_path, "w", encoding="utf-8") as f:
                    f.write(
                        "ZOOMIES THEME MODDING GUIDE\n"
                        "--------------------------\n"
                        "To create a custom theme, create a new folder here (e.g. themes/MyTheme) and place a 'theme.json' inside it.\n"
                        "You can configure colors, fonts, background images, and custom arrow textures.\n\n"
                        "See 'Example-Blue/theme.json' for the format configuration.\n"
                    )
            except Exception as e:
                print(f"Error writing theme modding readme: {e}")
                
        # Write ExampleTheme folder
        example_dir = os.path.join(self.themes_dir, "Example-Blue")
        if not os.path.exists(example_dir):
            try:
                os.makedirs(example_dir)
                example_json = {
                    "name": "Example-Blue",
                    "bg_color": [10, 15, 35],
                    "text_color": [220, 230, 255],
                    "accent_color": [0, 191, 255],
                    "lane_colors": [
                        [0, 150, 255],
                        [0, 200, 255],
                        [0, 255, 255],
                        [0, 100, 220],
                        [255, 255, 255]
                    ],
                    "arrow_type": "default"
                }
                with open(os.path.join(example_dir, "theme.json"), "w") as f:
                    json.dump(example_json, f, indent=4)
            except Exception as e:
                print(f"Error writing ExampleTheme template: {e}")
                
        # Scan themes folder
        try:
            for item_name in os.listdir(self.themes_dir):
                theme_path = os.path.join(self.themes_dir, item_name)
                if os.path.isdir(theme_path):
                    config_json = os.path.join(theme_path, "theme.json")
                    if os.path.exists(config_json):
                        with open(config_json, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        t_name = data.get("name", item_name)
                        self.custom_themes[t_name] = data
                        
                        assets = {}
                        
                        # Load custom background image
                        bg_img_file = data.get("bg_image")
                        if bg_img_file:
                            full_bg_path = os.path.join(theme_path, bg_img_file)
                            if os.path.exists(full_bg_path):
                                img = pygame.image.load(full_bg_path).convert()
                                assets["bg_image"] = img
                                
                        # Load custom arrow images
                        arrow_imgs = data.get("arrow_images")
                        if arrow_imgs:
                            assets["arrows"] = {}
                            idx_map = {"left": 0, "down": 1, "up": 2, "right": 3}
                            for dir_key, file_val in arrow_imgs.items():
                                if dir_key in idx_map:
                                    arrow_path = os.path.join(theme_path, file_val)
                                    if os.path.exists(arrow_path):
                                        assets["arrows"][idx_map[dir_key]] = pygame.image.load(arrow_path).convert_alpha()
                                        
                        # Load custom receptor images
                        rec_imgs = data.get("receptor_images")
                        if rec_imgs:
                            assets["receptors"] = {}
                            idx_map = {"left": 0, "down": 1, "up": 2, "right": 3}
                            for dir_key, file_val in rec_imgs.items():
                                if dir_key in idx_map:
                                    rec_path = os.path.join(theme_path, file_val)
                                    if os.path.exists(rec_path):
                                        assets["receptors"][idx_map[dir_key]] = pygame.image.load(rec_path).convert_alpha()
                                        
                        self.custom_theme_assets[t_name] = assets
                        print(f"Loaded mod theme: {t_name}")
        except Exception as e:
            print(f"Error scanning custom themes dir: {e}")

    def get_bg_color(self, theme):
        if theme in self.custom_themes:
            c = self.custom_themes[theme].get("bg_color")
            if c:
                return tuple(c)
        if theme == "DDR-Retro":
            return self.COLOR_BG_RETRO
        elif theme == "Minimalist":
            return self.COLOR_BG_MINIMAL
        elif theme == "Retro-Pixel":
            return (12, 10, 18)
        elif theme == "Futuristic":
            return (8, 6, 16)
        elif theme == "Kawaii-Pink":
            return (255, 230, 240)
        elif theme == "Neko-Pixel":
            return (35, 22, 45)
        return (18, 18, 22)

    def get_text_color(self, theme):
        if theme in self.custom_themes:
            c = self.custom_themes[theme].get("text_color")
            if c:
                return tuple(c)
        if theme in ["Minimalist", "Kawaii-Pink"]:
            return (45, 45, 55)
        return (255, 255, 255)

    def get_accent_color(self, theme):
        if theme in self.custom_themes:
            c = self.custom_themes[theme].get("accent_color")
            if c:
                return tuple(c)
        if theme in ["DDR-Retro", "Futuristic"]:
            return (0, 255, 204)  # Neon Cyan
        elif theme in ["Kawaii-Pink", "Neko-Pixel"]:
            return (255, 105, 180)  # Bright Pink
        elif theme == "Retro-Pixel":
            return (255, 255, 0)  # Retro Yellow
        return (0, 122, 255)      # iOS Blue

    def get_lane_color(self, lane, theme):
        l = lane % 5
        if theme in self.custom_themes:
            c_list = self.custom_themes[theme].get("lane_colors")
            if c_list and len(c_list) > l:
                return tuple(c_list[l])
        if theme == "Guitar-Hero" or settings.game_mode == "Guitar Hero":
            return self.HERO_LANE_COLORS[l]
        elif theme == "DDR-Retro":
            return self.RETRO_LANE_COLORS[l]
        elif theme == "Retro-Pixel":
            return self.RETRO_PIXEL_COLORS[l]
        elif theme == "Futuristic":
            return self.FUTURISTIC_COLORS[l]
        elif theme == "Kawaii-Pink":
            return self.KAWAII_PINK_COLORS[l]
        elif theme == "Neko-Pixel":
            return self.NEKO_PIXEL_COLORS[l]
        return self.MINIMAL_LANE_COLORS[l]

    def get_arrow_points(self, direction, x, y, scale=1.0):
        rotated = []
        d = direction % 4
        for px, py in self.base_arrow_points:
            if d == 2:    # UP
                rx, ry = px, py
            elif d == 3:  # RIGHT
                rx, ry = -py, px
            elif d == 1:  # DOWN
                rx, ry = -px, -py
            elif d == 0:  # LEFT
                rx, ry = py, -px
            
            rotated.append((x + rx * scale, y + ry * scale))
        return rotated

    def draw_heart_shape(self, surface, color, x, y, size):
        r = int(size * 0.3)
        pygame.draw.circle(surface, color, (int(x - r), int(y - r * 0.3)), r)
        pygame.draw.circle(surface, color, (int(x + r), int(y - r * 0.3)), r)
        points = [
            (int(x - 2 * r), int(y)),
            (int(x + 2 * r), int(y)),
            (int(x), int(y + size * 0.8))
        ]
        pygame.draw.polygon(surface, color, points)

    def draw_kitty_paw_shape(self, surface, color, x, y, size):
        # Large bottom pad
        pygame.draw.ellipse(surface, color, (x - size//3, y - size//5, size * 2//3, size * 4//10))
        # 3 round toes
        pygame.draw.circle(surface, color, (int(x - size//3), int(y - size//3.5)), int(size * 0.14))
        pygame.draw.circle(surface, color, (int(x), int(y - size//2.4)), int(size * 0.16))
        pygame.draw.circle(surface, color, (int(x + size//3), int(y - size//3.5)), int(size * 0.14))

    def draw_pixel_kitty_shape(self, surface, color, x, y, size):
        # Head box
        pygame.draw.rect(surface, color, (x - size//2, y - size//3, size, size * 7//10), border_radius=4)
        # Triangular ears
        left_ear = [(x - size//2, y - size//3), (x - size//3, y - size//3), (x - size//2, y - size//2 - 2)]
        right_ear = [(x + size//2, y - size//3), (x + size//3, y - size//3), (x + size//2, y - size//2 - 2)]
        pygame.draw.polygon(surface, color, left_ear)
        pygame.draw.polygon(surface, color, right_ear)
        # Inner ears (pink highlight)
        pygame.draw.polygon(surface, (255, 180, 200), [(x - size//2 + 3, y - size//3), (x - size//3.2, y - size//3), (x - size//2 + 3, y - size//2.5)])
        pygame.draw.polygon(surface, (255, 180, 200), [(x + size//2 - 3, y - size//3), (x + size//3.2, y - size//3), (x + size//2 - 3, y - size//2.5)])
        # Eyes
        pygame.draw.rect(surface, (10, 10, 10), (x - size//4 - 1, y - 1, 3, 3))
        pygame.draw.rect(surface, (10, 10, 10), (x + size//4 - 1, y - 1, 3, 3))
        # Cute pink nose
        pygame.draw.rect(surface, (255, 100, 150), (x - 1, y + 3, 2, 2))

    def draw_star_shape(self, surface, color, cx, cy, size, width=0):
        outer_r = size
        inner_r = size // 2
        pts = []
        for i in range(10):
            angle = i * math.pi / 5 - math.pi / 2
            r = outer_r if i % 2 == 0 else inner_r
            pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        pygame.draw.polygon(surface, color, pts, width)

    def draw_arrow(self, surface, x, y, direction, theme, scale=1.0, is_receptor=False, active_pulse=0.0, note_color=None):
        # Check for custom mod arrow asset
        assets = self.custom_theme_assets.get(theme)
        if assets:
            pulse_scale = 1.0 + (0.15 * active_pulse)
            scaled_sz = int(48 * scale * pulse_scale)
            
            img_surf = None
            if is_receptor and "receptors" in assets and direction in assets["receptors"]:
                img_surf = assets["receptors"][direction]
            elif "arrows" in assets and direction in assets["arrows"]:
                img_surf = assets["arrows"][direction]
                
            if img_surf:
                drawn_surf = pygame.transform.smoothscale(img_surf, (scaled_sz, scaled_sz))
                if is_receptor and ("receptors" not in assets or direction not in assets["receptors"]):
                    drawn_surf.fill((255, 255, 255, 120), special_flags=pygame.BLEND_RGBA_MULT)
                surface.blit(drawn_surf, (int(x - scaled_sz // 2), int(y - scaled_sz // 2)))
                return

        # Vector fallback rendering
        lane_color = self.get_lane_color(direction, theme)
        pulse_scale = 1.0 + (0.15 * active_pulse)
        scale *= pulse_scale
        size = int(24 * scale)

        if is_receptor:
            body_color = (255, 255, 255)
        else:
            body_color = note_color if note_color is not None else (255, 255, 255)

        outline_color = (15, 15, 18)

        if theme == "Guitar-Hero" or settings.game_mode == "Guitar Hero":
            radius = int(24 * scale)
            if is_receptor:
                pygame.draw.circle(surface, lane_color, (int(x), int(y)), radius + 5)
                pygame.draw.circle(surface, outline_color, (int(x), int(y)), radius + 2)
                pygame.draw.circle(surface, (255, 255, 255), (int(x), int(y)), radius - 1)
                pygame.draw.circle(surface, lane_color, (int(x), int(y)), radius - 8, width=3)
            else:
                pygame.draw.circle(surface, outline_color, (int(x), int(y)), radius + 2)
                pygame.draw.circle(surface, body_color, (int(x), int(y)), radius)
                pygame.draw.circle(surface, (255, 255, 255), (int(x), int(y)), radius - 6, width=2)

        elif theme == "Kawaii-Pink":
            if is_receptor:
                self.draw_heart_shape(surface, lane_color, x, y, size * 1.25)
                self.draw_heart_shape(surface, outline_color, x, y, size * 1.1)
                self.draw_heart_shape(surface, (255, 255, 255), x, y, size)
            else:
                self.draw_heart_shape(surface, outline_color, x, y, size * 1.1)
                self.draw_heart_shape(surface, body_color, x, y, size)
                self.draw_heart_shape(surface, (255, 255, 255), x, y, size * 0.6)

        elif theme == "Neko-Pixel":
            points_outer = self.get_arrow_points(direction, x, y, scale * 1.15)
            points_mid = self.get_arrow_points(direction, x, y, scale)
            points_inner = self.get_arrow_points(direction, x, y, scale * 0.7)
            
            left_ear = [(x - 14*scale, y - 8*scale), (x - 6*scale, y - 8*scale), (x - 14*scale, y - 18*scale)]
            right_ear = [(x + 14*scale, y - 8*scale), (x + 6*scale, y - 8*scale), (x + 14*scale, y - 18*scale)]
            pygame.draw.polygon(surface, outline_color, [(p[0], p[1]-1) for p in left_ear])
            pygame.draw.polygon(surface, outline_color, [(p[0], p[1]-1) for p in right_ear])
            
            ear_color = lane_color if is_receptor else body_color
            pygame.draw.polygon(surface, ear_color, left_ear)
            pygame.draw.polygon(surface, ear_color, right_ear)
            
            if is_receptor:
                pygame.draw.polygon(surface, lane_color, points_outer)
                pygame.draw.polygon(surface, outline_color, points_mid)
                pygame.draw.polygon(surface, (255, 255, 255), points_inner)
            else:
                pygame.draw.polygon(surface, outline_color, points_outer)
                pygame.draw.polygon(surface, body_color, points_mid)
                pygame.draw.polygon(surface, (255, 255, 255), points_inner, width=2)

        else:
            points_glow = self.get_arrow_points(direction, x, y, scale * 1.3)
            points_outer = self.get_arrow_points(direction, x, y, scale * 1.15)
            points_mid = self.get_arrow_points(direction, x, y, scale)
            points_inner = self.get_arrow_points(direction, x, y, scale * 0.7)

            if is_receptor:
                pygame.draw.polygon(surface, lane_color, points_glow, width=3)
                pygame.draw.polygon(surface, outline_color, points_outer)
                pygame.draw.polygon(surface, (255, 255, 255), points_mid)
                pygame.draw.polygon(surface, lane_color, points_inner, width=2)
            else:
                pygame.draw.polygon(surface, outline_color, points_outer)
                pygame.draw.polygon(surface, body_color, points_mid)
                pygame.draw.polygon(surface, (255, 255, 255), points_inner, width=2)

    def draw_background_grid(self, surface, theme, beat_progress=0.0):
        w, h = surface.get_size()
        
        # Check for custom background image
        assets = self.custom_theme_assets.get(theme)
        if assets and "bg_image" in assets:
            bg_surf = assets["bg_image"]
            if bg_surf.get_size() != (w, h):
                assets["bg_image"] = pygame.transform.smoothscale(bg_surf, (w, h))
                bg_surf = assets["bg_image"]
            surface.blit(bg_surf, (0, 0))
            
            # Subtle scrolling grid lines overlay
            for gx in range(w // 2 - 200, w // 2 + 201, 100):
                pygame.draw.line(surface, (60, 55, 75, 40), (gx, 0), (gx, h), 1)
            scroll_y = int((beat_progress % 1.0) * 80)
            for gy in range(scroll_y, h, 80):
                pygame.draw.line(surface, (60, 55, 75, 25), (0, gy), (w, gy), 1)
            return

        if theme == "DDR-Retro":
            grid_color = (30, 20, 50)
            beat_pulse = int(10 * math.sin(beat_progress * math.pi))
            pulse_color = (
                max(0, min(255, grid_color[0] + beat_pulse)),
                max(0, min(255, grid_color[1] + beat_pulse * 2)),
                max(0, min(255, grid_color[2] + beat_pulse * 3))
            )
            pygame.draw.line(surface, pulse_color, (w // 2 - 200, 0), (w // 2 - 200, h), 1)
            pygame.draw.line(surface, pulse_color, (w // 2 - 100, 0), (w // 2 - 100, h), 1)
            pygame.draw.line(surface, pulse_color, (w // 2, 0), (w // 2, h), 2)
            pygame.draw.line(surface, pulse_color, (w // 2 + 100, 0), (w // 2 + 100, h), 1)
            pygame.draw.line(surface, pulse_color, (w // 2 + 200, 0), (w // 2 + 200, h), 1)
            
            scroll_y = int((beat_progress % 1.0) * 80)
            for y in range(scroll_y, h, 80):
                fade = max(0.1, 1.0 - abs(y - h/2) / (h/2))
                y_color = (int(pulse_color[0] * fade), int(pulse_color[1] * fade), int(pulse_color[2] * fade))
                pygame.draw.line(surface, y_color, (0, y), (w, y), 1)

        elif theme == "Retro-Pixel":
            random.seed(42)
            for i in range(15):
                star_x = int((random.random() * 0.9 + 0.05) * w)
                star_y = int((random.random() * 0.9 + 0.05) * h)
                twinkle = (math.sin(beat_progress * 4.0 + i) + 1.0) / 2.0
                if twinkle > 0.4:
                    col = (0, 255, 204) if i % 2 == 0 else (255, 0, 128)
                    pygame.draw.rect(surface, col, (star_x, star_y, 6, 6))
            grid_y_start = int((beat_progress % 1.0) * 60)
            for gy in range(grid_y_start, h, 60):
                pygame.draw.line(surface, (40, 30, 60), (0, gy), (w, gy), 2)

        elif theme == "Futuristic":
            horizon_y = 250
            pygame.draw.rect(surface, (10, 5, 20), (0, 0, w, h))
            pygame.draw.line(surface, (255, 0, 128), (0, horizon_y), (w, horizon_y), 3)
            
            num_lines = 14
            for i in range(num_lines):
                angle = math.pi * (0.1 + 0.8 * (i / (num_lines - 1)))
                end_x = w // 2 + 1000 * math.cos(angle)
                end_y = horizon_y + 1000 * math.sin(angle)
                pygame.draw.line(surface, (0, 255, 204), (w // 2, horizon_y), (end_x, end_y), 1)
                
            scroll = (beat_progress % 1.0)
            for i in range(12):
                y_factor = ((i + scroll) / 12.0) ** 2.0
                line_y = horizon_y + y_factor * (h - horizon_y)
                alpha_factor = y_factor
                col = (int(255 * alpha_factor), 0, int(128 * alpha_factor))
                pygame.draw.line(surface, col, (0, line_y), (w, line_y), 2)

        elif theme == "Kawaii-Pink":
            random.seed(123)
            for i in range(12):
                x_pos = int((random.random() * 0.9 + 0.05) * w)
                y_pos = int((h - (beat_progress * 50 + i * 80)) % h)
                bob = math.sin(beat_progress * 2.0 + i) * 15
                self.draw_heart_shape(surface, (255, 180, 200), x_pos + bob, y_pos, 22)

        elif theme == "Neko-Pixel":
            random.seed(999)
            for i in range(10):
                px_x = int((random.random() * 0.8 + 0.1) * w)
                px_y = int((random.random() * 0.8 + 0.1) * h)
                scale = 1.0 + 0.15 * math.sin(beat_progress * math.pi + i)
                col = (255, 105, 180) if i % 2 == 0 else (186, 85, 211)
                self.draw_kitty_paw_shape(surface, col, px_x, px_y, int(18 * scale))
                
        elif theme == "Guitar-Hero":
            highway_color = (20, 20, 24)
            pygame.draw.rect(surface, highway_color, (w // 2 - 220, 0, 440, h))
            pygame.draw.line(surface, (180, 180, 190), (w // 2 - 222, 0), (w // 2 - 222, h), 4)
            pygame.draw.line(surface, (180, 180, 190), (w // 2 + 222, 0), (w // 2 + 222, h), 4)
            pygame.draw.line(surface, (60, 60, 65), (w // 2 - 110, 0), (w // 2 - 110, h), 2)
            pygame.draw.line(surface, (100, 100, 105), (w // 2, 0), (w // 2, h), 2)
            pygame.draw.line(surface, (60, 60, 65), (w // 2 + 110, 0), (w // 2 + 110, h), 2)
            
            scroll_y = int((beat_progress % 1.0) * 100)
            for gy in range(scroll_y, h, 100):
                pygame.draw.line(surface, (45, 45, 50), (w // 2 - 220, gy), (w // 2 + 220, gy), 2)
                
        else:
            pygame.draw.rect(surface, (235, 235, 240), (w // 2 - 220, 0, 440, h))
            pygame.draw.line(surface, (220, 220, 225), (w // 2, 0), (w // 2, h), 1)

theme_manager = ThemeManager()
