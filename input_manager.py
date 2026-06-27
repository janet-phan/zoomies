import pygame
from config import settings

class InputManager:
    def __init__(self):
        self.joysticks = []
        
        # Track button states to prevent duplicate triggering
        self.key_states = {
            "left": False,
            "down": False,
            "up": False,
            "right": False
        }
        
        # Temporary mapping helper for remapping screen
        self.remapping_active = False
        self.remap_target = None  # "left", "down", "up", or "right"
        self.remap_callback = None

    def refresh_joysticks(self):
        pygame.joystick.init()
        self.joysticks = []
        count = pygame.joystick.get_count()
        print(f"[JOYSTICK LOG] refresh_joysticks called. Found {count} joysticks.")
        for i in range(count):
            try:
                joy = pygame.joystick.Joystick(i)
                joy.init()
                self.joysticks.append(joy)
                print(f"[JOYSTICK LOG] Initialized joystick {i}: {joy.get_name()} (Axes: {joy.get_numaxes()}, Buttons: {joy.get_numbuttons()})")
            except Exception as e:
                print(f"[JOYSTICK LOG] Failed to initialize joystick {i}: {e}")

    def get_gamepad_name(self):
        if self.joysticks:
            return self.joysticks[0].get_name()
        return "None Detected"

    def start_remap(self, direction, callback):
        """Starts listening for the next key/button to bind to the specified direction."""
        self.remapping_active = True
        self.remap_target = direction
        self.remap_callback = callback

    def cancel_remap(self):
        self.remapping_active = False
        self.remap_target = None
        self.remap_callback = None

    def handle_event(self, event):
        """
        Process a pygame event.
        Returns a tuple (direction, is_down, is_keyboard, input_desc) if a mapped button matches,
        or None.
        Also handles remapping if active.
        """
        if self.remapping_active:
            result = self._process_remap_event(event)
            if result:
                # Successfully remapped
                self.remapping_active = False
                self.remap_target = None
                if self.remap_callback:
                    self.remap_callback(result)
                return None

        # Standard Gameplay / Navigation handling
        # Keyboard Events
        if event.type == pygame.KEYDOWN or event.type == pygame.KEYUP:
            is_down = (event.type == pygame.KEYDOWN)
            key_id = event.key
            for dir_name, mapped_key in settings.keys.items():
                if key_id == mapped_key:
                    self.key_states[dir_name] = is_down
                    # Describe key
                    key_name = pygame.key.name(key_id).upper()
                    return dir_name, is_down, True, key_name

        # Gamepad Button Events
        if event.type == pygame.JOYBUTTONDOWN or event.type == pygame.JOYBUTTONUP:
            is_down = (event.type == pygame.JOYBUTTONDOWN)
            btn_id = event.button
            gp_settings = settings.gamepad
            for dir_name in ["left", "down", "up", "right"]:
                map_val = gp_settings.get(dir_name)
                # Check if it matches button binding
                if isinstance(map_val, dict) and map_val.get("type") == "button":
                    if btn_id == map_val.get("id"):
                        return dir_name, is_down, False, f"Btn {btn_id}"
                elif not isinstance(map_val, dict) and btn_id == map_val:
                    # Legacy integer mapping support
                    return dir_name, is_down, False, f"Btn {btn_id}"

        # Gamepad Hat Events (D-pads)
        if event.type == pygame.JOYHATMOTION:
            gp_settings = settings.gamepad
            hat_val = event.value  # tuple (x, y) e.g. (-1, 0) for left
            for dir_name in ["left", "down", "up", "right"]:
                map_val = gp_settings.get(dir_name)
                if isinstance(map_val, dict) and map_val.get("type") == "hat":
                    target_hat = map_val.get("hat_idx", 0)
                    if event.hat == target_hat:
                        target_val = map_val.get("value") # [x, y]
                        # Check if the hat matches the target direction
                        is_active = False
                        if target_val[0] != 0 and hat_val[0] == target_val[0]:
                            is_active = True
                        if target_val[1] != 0 and hat_val[1] == target_val[1]:
                            is_active = True
                        
                        # Return state change
                        return dir_name, is_active, False, f"D-Pad {dir_name.upper()}"

        # Gamepad Axis Events (Analog Sticks)
        if event.type == pygame.JOYAXISMOTION:
            gp_settings = settings.gamepad
            axis_val = event.value
            for dir_name in ["left", "down", "up", "right"]:
                map_val = gp_settings.get(dir_name)
                if isinstance(map_val, dict) and map_val.get("type") == "axis":
                    target_axis = map_val.get("axis_idx")
                    if event.axis == target_axis:
                        target_sign = map_val.get("sign") # -1 or 1
                        is_active = (axis_val * target_sign > 0.5) # Deadzone of 0.5
                        return dir_name, is_active, False, f"Axis {target_axis} {'+' if target_sign > 0 else '-'}"

        return None

    def _process_remap_event(self, event):
        """Helper to capture the next valid input event and format it for settings."""
        if event.type in [pygame.KEYDOWN, pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION, pygame.JOYAXISMOTION]:
            print(f"[REMAP DEBUG] Target: {self.remap_target} | Received event: {event}")
            
        # 1. Keyboard Key Press (always allowed as fallback / escape)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.cancel_remap()
                return None
            return {"type": "keyboard", "key": event.key, "desc": pygame.key.name(event.key).upper()}

        target = (self.remap_target or "").lower()
        
        # 2. Gamepad Button Press (allowed for frets, strum, whammy, tilt)
        if event.type == pygame.JOYBUTTONDOWN:
            val = {
                "type": "button",
                "id": event.button
            }
            return {"type": "gamepad", "map_val": val, "desc": f"Gamepad Btn {event.button}"}

        # 3. Gamepad Hat Movement (only allowed for strum, D-pads/navigation)
        if event.type == pygame.JOYHATMOTION:
            is_strum = (target == "strum")
            is_navigation = target in ["left", "down", "up", "right"]
            if is_strum or is_navigation:
                hat_val = event.value
                if hat_val != (0, 0):
                    x, y = hat_val
                    val = {
                        "type": "hat",
                        "hat_idx": event.hat,
                        "value": [x, y]
                    }
                    dir_desc = "Left" if x < 0 else "Right" if x > 0 else "Down" if y < 0 else "Up"
                    return {"type": "gamepad", "map_val": val, "desc": f"D-Pad {dir_desc}"}

        # 4. Gamepad Axis Movement (ONLY allowed for whammy and tilt!)
        if event.type == pygame.JOYAXISMOTION:
            is_analog = target in ["whammy", "tilt"]
            if is_analog:
                axis_val = event.value
                if abs(axis_val) > 0.7:  # High threshold for intentional mapping
                    sign = 1 if axis_val > 0 else -1
                    val = {
                        "type": "axis",
                        "axis_idx": event.axis,
                        "sign": sign
                    }
                    return {"type": "gamepad", "map_val": val, "desc": f"Axis {event.axis} {'+' if sign > 0 else '-'}"}

        return None

input_manager = InputManager()
