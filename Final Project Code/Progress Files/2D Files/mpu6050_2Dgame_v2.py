# Malik F (mhf68) & Hetao Y (hy668)
# 2Dgame v2
# Added on screen HUD for telemetry, and more detailed drone drawing. 
# November 17, 2025

import pygame
import pigame
import math
import time
import os
import sys

# piTFT display variables
os.putenv('SDL_VIDEODRIVER', 'fbcon')
os.putenv('SDL_FBDEV', '/dev/fb0') #fb0 for other display
os.putenv('SDL_MOUSEDRV', 'dummy')
os.putenv('SDL_MOUSEDEV', '/dev/null')
os.putenv('DISPLAY', '')

pygame.init()
pygame.mouse.set_visible(False)
pitft = pigame.PiTft()

# Import MPU file
import mpu6050_calibrate_v4 as mpu  

# Screen resolution (can be 320x240 or 800x480 depending on display)
WIDTH, HEIGHT = 800, 480
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Drone Controlled by MPU6050")

clock = pygame.time.Clock()

# Drone state
x = WIDTH // 2
y = HEIGHT // 2
yaw_angle = 0

MOVE_SPEED = 0.5
YAW_SENS = 0.5

font = pygame.font.SysFont("consolas", 22)

# Draw drone more detailed
def draw_drone(surface, cx, cy, angle):
    rad = math.radians(angle)

    def rot(px, py):
        rx = px * math.cos(rad) - py * math.sin(rad)
        ry = px * math.sin(rad) + py * math.cos(rad)
        return (cx + rx, cy + ry)

    # Drone arms
    pygame.draw.line(surface, (180, 180, 255), rot(-40, 0), rot(40, 0), 6)
    pygame.draw.line(surface, (180, 180, 255), rot(0, -40), rot(0, 40), 6)

    # Drone center body
    pygame.draw.circle(surface, (80, 120, 220), (int(cx), int(cy)), 18)

    # Rotors
    for px, py in [(40, 0), (-40, 0), (0, 40), (0, -40)]:
        rx, ry = rot(px, py)
        pygame.draw.circle(surface, (220, 80, 80), (int(rx), int(ry)), 12)


# HUD for screen
def draw_hud(surface, roll, pitch, yaw):
    text1 = font.render(f"Roll :  {roll:6.2f}°", True, (255, 255, 255))
    text2 = font.render(f"Pitch:  {pitch:6.2f}°", True, (255, 255, 255))
    text3 = font.render(f"Yaw  :  {yaw:6.2f}°", True, (255, 255, 255))

    surface.blit(text1, (10, 10))
    surface.blit(text2, (10, 40))
    surface.blit(text3, (10, 70))

# Main Loop
mpu.mpu_setup_once() # call once for pygame

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Read MPU data
    roll, pitch, yaw_rate = mpu.get_mpu_orientation()

    # Update yaw
    yaw_angle += yaw_rate * YAW_SENS

    # Map pitch/roll to planar motion
    forward = -pitch * MOVE_SPEED
    strafe = roll * MOVE_SPEED

    rad = math.radians(yaw_angle)

    dx = forward * math.sin(rad) + strafe * math.cos(rad)
    dy = forward * -math.cos(rad) + strafe * math.sin(rad)

    x += dx
    y += dy

    x = max(0, min(WIDTH, x))
    y = max(0, min(HEIGHT, y))

    # Draw frame
    screen.fill((20, 20, 25))
    draw_drone(screen, x, y, yaw_angle)
    draw_hud(screen, roll, pitch, yaw_angle)

    pygame.display.flip()
    clock.tick(60)

# Cleanup
del(pitft)
pygame.quit()
sys.exit(0)

