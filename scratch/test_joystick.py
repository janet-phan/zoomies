import pygame
import sys
import time

pygame.init()
pygame.joystick.init()

print("Scanning for joysticks...")
count = pygame.joystick.get_count()
print(f"Number of joysticks detected: {count}")

joysticks = []
for i in range(count):
    joy = pygame.joystick.Joystick(i)
    joy.init()
    joysticks.append(joy)
    print(f"Joystick {i}: {joy.get_name()} | Axes: {joy.get_numaxes()} | Buttons: {joy.get_numbuttons()} | Hats: {joy.get_numhats()}")

if count == 0:
    print("No joysticks found! Please plug in your controller and try again.")
    sys.exit()

print("\nPress buttons or move sticks on your controller. Press Ctrl+C to exit.")
print("Watching for events...")

try:
    while True:
        pygame.event.pump()
        for event in pygame.event.get():
            if event.type == pygame.JOYBUTTONDOWN:
                print(f"[BUTTON DOWN] Joystick {event.joy} Button {event.button}")
            elif event.type == pygame.JOYBUTTONUP:
                print(f"[BUTTON UP] Joystick {event.joy} Button {event.button}")
            elif event.type == pygame.JOYAXISMOTION:
                if abs(event.value) > 0.1:  # ignore noise
                    print(f"[AXIS MOTION] Joystick {event.joy} Axis {event.axis} Value {event.value:.3f}")
            elif event.type == pygame.JOYHATMOTION:
                print(f"[HAT MOTION] Joystick {event.joy} Hat {event.hat} Value {event.value}")
        time.sleep(0.01)
except KeyboardInterrupt:
    print("\nExiting.")
