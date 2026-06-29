import pygame
import random
import math

class ConfettiParticle:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.x = random.randint(0, w)
        self.y = random.randint(-50, -10)
        self.size = random.randint(6, 12)
        self.color = random.choice([
            (255, 50, 50), (50, 255, 50), (50, 50, 255),
            (255, 215, 0), (255, 0, 255), (0, 255, 255),
            (255, 128, 0), (255, 255, 255)
        ])
        self.vy = random.uniform(2.0, 5.0)
        self.vx = random.uniform(-1.5, 1.5)
        self.angle = random.uniform(0, 360)
        self.rotation_speed = random.uniform(-5.0, 5.0)
        self.sway_speed = random.uniform(2.0, 4.0)
        self.sway_amp = random.uniform(1.0, 3.0)
        self.spawn_time = random.uniform(0, 100)

    def update(self, dt):
        self.y += self.vy * dt * 60.0
        self.x += (self.vx + math.sin(self.y * 0.05 + self.spawn_time) * self.sway_amp) * dt * 60.0
        self.angle += self.rotation_speed * dt * 60.0

    def draw(self, surface):
        # Draw a rotated rectangle for confetti piece
        conf_surf = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        conf_surf.fill(self.color)
        rot_surf = pygame.transform.rotate(conf_surf, self.angle)
        surface.blit(rot_surf, (self.x - rot_surf.get_width() // 2, self.y - rot_surf.get_height() // 2))

class FireworkSpark:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(2.0, 7.0)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.gravity = 0.12
        self.friction = 0.96
        self.alpha = 255
        self.fade_speed = random.uniform(3.0, 6.0)
        self.size = random.uniform(2.0, 4.0)

    def update(self, dt):
        self.vx *= self.friction
        self.vy *= self.friction
        self.vy += self.gravity
        self.x += self.vx * dt * 60.0
        self.y += self.vy * dt * 60.0
        self.alpha = max(0, self.alpha - self.fade_speed * dt * 60.0)

    def draw(self, surface):
        if self.alpha <= 0:
            return
        spark_surf = pygame.Surface((int(self.size * 2), int(self.size * 2)), pygame.SRCALPHA)
        # Apply alpha to color
        c = (self.color[0], self.color[1], self.color[2], int(self.alpha))
        pygame.draw.circle(spark_surf, c, (int(self.size), int(self.size)), int(self.size))
        surface.blit(spark_surf, (self.x - self.size, self.y - self.size))

class FireworkRocket:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.x = random.randint(100, w - 100)
        self.y = h + 10
        self.target_y = random.randint(100, h // 2)
        self.vy = random.uniform(-8.0, -12.0)
        self.vx = random.uniform(-1.0, 1.0)
        self.exploded = False
        self.color = random.choice([
            (255, 50, 50), (50, 255, 50), (50, 50, 255),
            (255, 215, 0), (255, 0, 255), (0, 255, 255),
            (255, 128, 0)
        ])
        self.trail = []

    def update(self, dt, sparks):
        self.x += self.vx * dt * 60.0
        self.y += self.vy * dt * 60.0
        self.trail.append((self.x, self.y))
        self.trail = self.trail[-6:]
        
        if self.vy < 0:
            self.vy += 0.05  # decelerate upwards
            
        if self.y <= self.target_y or self.vy >= 0:
            self.exploded = True
            # Spawn explosion sparks!
            num_sparks = random.randint(40, 60)
            for _ in range(num_sparks):
                sparks.append(FireworkSpark(self.x, self.y, self.color))

    def draw(self, surface):
        if self.exploded:
            return
        # Draw rocket trail
        for idx, pos in enumerate(self.trail):
            alpha = int((idx / len(self.trail)) * 180)
            sz = max(1, int((idx / len(self.trail)) * 3))
            dot = pygame.Surface((sz*2, sz*2), pygame.SRCALPHA)
            dot.fill((self.color[0], self.color[1], self.color[2], alpha))
            surface.blit(dot, (pos[0]-sz, pos[1]-sz))

class CelebrationSystem:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.confetti = []
        self.rockets = []
        self.sparks = []
        self.active = False
        self.timer = 0.0

    def trigger(self):
        self.active = True
        self.timer = 6.0  # Show celebration for 6 seconds
        self.confetti = [ConfettiParticle(self.w, self.h) for _ in range(120)]
        self.rockets = [FireworkRocket(self.w, self.h) for _ in range(4)]
        self.sparks = []

    def update(self, dt):
        if not self.active:
            return
        self.timer -= dt
        if self.timer <= 0:
            self.active = False
            self.confetti.clear()
            self.rockets.clear()
            self.sparks.clear()
            return

        # Update Confetti
        for c in self.confetti:
            c.update(dt)
            if c.y > self.h:
                # Reset to top
                c.y = random.randint(-40, -10)
                c.x = random.randint(0, self.w)

        # Update Rockets
        for r in list(self.rockets):
            r.update(dt, self.sparks)
            if r.exploded:
                self.rockets.remove(r)

        # Periodically spawn new rockets
        if len(self.rockets) < 2 and random.random() < 0.02 * (dt * 60.0) and self.timer > 2.0:
            self.rockets.append(FireworkRocket(self.w, self.h))

        # Update Sparks
        for s in list(self.sparks):
            s.update(dt)
            if s.alpha <= 0:
                self.sparks.remove(s)

    def draw(self, surface):
        if not self.active:
            return
        for c in self.confetti:
            c.draw(surface)
        for r in self.rockets:
            r.draw(surface)
        for s in self.sparks:
            s.draw(surface)
