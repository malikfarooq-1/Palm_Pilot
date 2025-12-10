# Malik F (mhf68) & Hetao Y (hy668)
# Basic 3D static rendering v1
# Added basic 3D projection (rotate point and project point), simple staic 3D drone.
# November 21, 2025

import pygame
import pigame
import math
import sys
import os

# Display setup
os.putenv('SDL_VIDEODRIVER', 'fbcon')
os.putenv('SDL_FBDEV', '/dev/fb0') 
os.putenv('SDL_MOUSEDRV', 'dummy')
os.putenv('SDL_MOUSEDEV', '/dev/null')
os.putenv('DISPLAY', '')

pygame.init()
pygame.mouse.set_visible(False)
pitft = pigame.PiTft()

# Import MPU script
import mpu6050_calibrate_v4 as mpu

# Screen Settings
WIDTH, HEIGHT = 800, 480
CX, CY = WIDTH // 2, HEIGHT // 2  # Center of screen
FOV = 600  # Field of View (Camera distance)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("MPU6050 3D Visualizer")
clock = pygame.time.Clock()

font = pygame.font.SysFont("consolas", 22)

# Drone drawing (used AI for idea of points)
vertices = [
    (-10, -3, 15), (10, -3, 15), (10, 3, 15), (-10, 3, 15), # Front Face (0-3)
    (-10, -3, -15), (10, -3, -15), (10, 3, -15), (-10, 3, -15), # Back Face (4-7)
    (-30, 0, 30), (30, 0, 30), (30, 0, -30), (-30, 0, -30) # Arms tip (8-11)
]

# Scaling for size
SCALE = 3.5

# 3D movement function
def rotate_point(x, y, z, roll, pitch, yaw):
  
    # Convert to radians
    r = math.radians(roll)
    p = math.radians(pitch)
    y_rad = math.radians(yaw)
    
    # Rotation X (Pitch)
    rx = x
    ry = y * math.cos(p) - z * math.sin(p)
    rz = y * math.sin(p) + z * math.cos(p)
    x, y, z = rx, ry, rz

    # Rotation Y (Yaw)
    rx = x * math.cos(y_rad) + z * math.sin(y_rad)
    ry = y
    rz = -x * math.sin(y_rad) + z * math.cos(y_rad)
    x, y, z = rx, ry, rz

    # Rotation Z (Roll)
    rx = x * math.cos(r) - y * math.sin(r)
    ry = x * math.sin(r) + y * math.cos(r)
    rz = z
    x, y, z = rx, ry, rz
    
    return x, y, z

# Draw points on screen in 3D
def project_point(x, y, z):
    # Pushes object into screen
    factor = FOV / (FOV + z + 400) 
    
    x_2d = x * factor + CX
    y_2d = -y * factor + CY # -y for screen being backward
    
    return int(x_2d), int(y_2d)

# Function to draw HUD
def draw_hud(surface, r, p, y):
    text = font.render(f"R: {r:.1f}  P: {p:.1f}  Y: {y:.1f}", True, (0, 255, 0))
    surface.blit(text, (10, 10))
    
    lbl = font.render("3D VIEW", True, (100, 100, 255))
    surface.blit(lbl, (WIDTH - 100, 10))


# Main loop
mpu.mpu_setup_once()

try:
    while True:
        # Background draw
        screen.fill((20, 20, 20))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        # MPU data
        roll_raw, pitch_raw, yaw_raw = mpu.get_mpu_orientation()
        
        r = -roll_raw
        p = pitch_raw
        y = -yaw_raw 

        # Make 3D points
        projected_points = []
        
        for v in vertices:
            # Scale
            x = v[0] * SCALE
            y = v[1] * SCALE
            z = v[2] * SCALE
            
            # Rotate
            rx, ry, rz = rotate_point(x, y, z, r, p, y)
            
            # Project
            px, py = project_point(rx, ry, rz)
            projected_points.append((px, py))

        # Draw motors
        c_arm = (80, 80, 80)
        
        # Front Arms
        pygame.draw.line(screen, c_arm, projected_points[0], projected_points[8], 6)
        pygame.draw.line(screen, c_arm, projected_points[1], projected_points[9], 6)
        
        # Back Arms
        pygame.draw.line(screen, c_arm, projected_points[4], projected_points[11], 6)
        pygame.draw.line(screen, c_arm, projected_points[5], projected_points[10], 6)
        
        # Motors: Front is red, back is green
        pygame.draw.circle(screen, (200, 50, 50), projected_points[8], 8)  # FL Red
        pygame.draw.circle(screen, (200, 50, 50), projected_points[9], 8)  # FR Red
        pygame.draw.circle(screen, (50, 200, 50), projected_points[10], 8) # BL Green
        pygame.draw.circle(screen, (50, 200, 50), projected_points[11], 8) # BR Green
        
        # Main body
        # Top face points: 0, 1, 5, 4
        body_poly = [projected_points[0], projected_points[1], projected_points[5], projected_points[4]]
        pygame.draw.polygon(screen, (30, 100, 160), body_poly) # Fill shape
        pygame.draw.polygon(screen, (200, 200, 200), body_poly, 1) # Outline
        
        # Front indication
        nose_x = (projected_points[0][0] + projected_points[1][0]) // 2
        nose_y = (projected_points[0][1] + projected_points[1][1]) // 2
        pygame.draw.circle(screen, (50, 50, 255), (nose_x, nose_y), 4)

        draw_hud(screen, roll_raw, pitch_raw, yaw_raw)
        
        pygame.display.flip()
        clock.tick(60)

# Cleanup and exit
except KeyboardInterrupt:
    print("Exiting...")
    pygame.quit()
    sys.exit()