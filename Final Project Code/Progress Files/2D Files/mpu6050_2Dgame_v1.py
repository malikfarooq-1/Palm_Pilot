# Malik F (mhf68) & Hetao Y (hy668)
# Basic animation with MPU integration v1
# Added sensor reading with drone movement integration and simple drawing.
# November 17, 2025

import pygame
import pigame
import math
import time
import os
import sys

# piTFT display variables
os.putenv('SDL_VIDEODRIVER', 'fbcon')
os.putenv('SDL_FBDEV', '/dev/fb1') #fb0 for other display
os.putenv('SDL_MOUSEDRV', 'dummy')
os.putenv('SDL_MOUSEDEV', '/dev/null')
os.putenv('DISPLAY', '')

pygame.init()
pygame.mouse.set_visible(False)
pitft = pigame.PiTft()

# Import MPU file
import mpu6050_calibrate_v4 as mpu  

# Screen resolution (can be 320x240 or 800x480 depending on display)
WIDTH, HEIGHT = 320, 240
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Drone Controlled by MPU6050")

clock = pygame.time.Clock()

# Drone state
x = WIDTH // 2
y = HEIGHT // 2
yaw_angle = 0

MOVE_SPEED = 0.5
YAW_SENS = 0.5

# Drone drawing function (basic)
def draw_drone(surface, cx, cy, angle):
    rad = math.radians(angle)

    def rot(px, py):
        rx = px * math.cos(rad) - py * math.sin(rad)
        ry = px * math.sin(rad) + py * math.cos(rad)
        return (cx + rx, cy + ry)

    body = [rot(-20, -10), rot(20, -10), rot(20, 10), rot(-20, 10)]
    
    pygame.draw.polygon(surface, (100, 180, 255), body)

    # Rotors
    for px, py in [(35, 0), (-35, 0), (0, 35), (0, -35)]:
        rx, ry = rot(px, py)
        pygame.draw.circle(surface, (250, 120, 120), (int(rx), int(ry)), 8)


# Main Loop
mpu.mpu_setup_once() # call once for pygame

running = True
while running:
    pitft.update() 

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:  # press ESC to quit
                running = False

    # Read MPU data
    roll, pitch, yaw_rate = mpu.get_mpu_orientation()

    # Update yaw
    yaw_angle += yaw_rate * YAW_SENS

    # Movement (pitch forward/back, roll left/right)
    forward = -pitch * MOVE_SPEED
    strafe = roll * MOVE_SPEED

    # Convert movement based on yaw angle
    rad = math.radians(yaw_angle)
    dx = forward * math.sin(rad) + strafe * math.cos(rad)
    dy = forward * -math.cos(rad) + strafe * math.sin(rad)

    x += dx
    y += dy

    # Keep drone inside screen
    x = max(0, min(WIDTH, x))
    y = max(0, min(HEIGHT, y))

    # Draw frame
    screen.fill((20, 20, 25))
    draw_drone(screen, x, y, yaw_angle)

    pygame.display.flip()
    clock.tick(60)

# Cleanup
del(pitft)
pygame.quit()
sys.exit(0)

