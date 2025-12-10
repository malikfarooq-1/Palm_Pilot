# Malik F (mhf68) & Hetao Y (hy668)
# 3D Free Roam in Grid v2
# Added infinite grid, moved camera (x and z axis now), basic velocity/friction from 2D files.
# Removed static rendering, fixed camera angle (x and z axis now).
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
CX, CY = WIDTH // 2, HEIGHT // 2
FOV = 500  # Field of View

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Drone 3D Free Roam")
clock = pygame.time.Clock()
font = pygame.font.SysFont("consolas", 18)

# Initialized variables for camera view
cam_x = 0.0
cam_y = -100.0 
cam_z = 0.0
vel_x = 0.0
vel_z = 0.0
ACCEL = 1.5
FRICTION = 0.92
MAX_SPEED = 40.0

# Projection method function
def project(x, y, z):
    if z < 1: z = 1 
    scale = FOV / (FOV + z)
    px = x * scale + CX
    py = -y * scale + CY 
    return int(px), int(py), scale

# Rotation function
def rotate_y(x, z, angle_rad):
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    rx = x * cos_a - z * sin_a
    rz = x * sin_a + z * cos_a
    return rx, rz

# Combined rotation function
def rotate_3d(x, y, z, r, p, yw):
    
    # Combined rotation for model
    rx = x * math.cos(yw) + z * math.sin(yw)
    rz = z * math.cos(yw) - x * math.sin(yw)
    x, z = rx, rz
    ry = y * math.cos(p) - z * math.sin(p)
    rz = y * math.sin(p) + z * math.cos(p)
    y, z = ry, rz
    rx = x * math.cos(r) - y * math.sin(r)
    ry = x * math.sin(r) + y * math.cos(r)
    x, y = rx, ry
    return x, y, z

# Same model from previous
drone_verts = [
    (-10, -3, 15), (10, -3, 15), (10, 3, 15), (-10, 3, 15), # Front Face (0-3)
    (-10, -3, -15), (10, -3, -15), (10, 3, -15), (-10, 3, -15), # Back Face (4-7)
    (-30, 0, 30), (30, 0, 30), (30, 0, -30), (-30, 0, -30) # Arms tip (8-11)
]

# Draw drone
def draw_drone(surface, roll, pitch, yaw):
    # 180 offset in front
    model_z_offset = 180 
    
    # Convert angles to radians
    r_rad = math.radians(roll)
    p_rad = math.radians(pitch)
    y_rad = math.radians(yaw) 

    transformed_points = []
    
    for v in drone_verts:
        x, y, z = v
        
        # Rotate model
        x, y, z = rotate_3d(x, y, z, -r_rad, p_rad, y_rad)

        # Map to camera position
        z += model_z_offset
        y += 20 
        
        px, py, scale = project(x, y, z)
        transformed_points.append((px, py))
    
    # Arms shape
    c_arm = (80, 80, 80)

    # Front Arms: 0->8, 1->9
    pygame.draw.line(surface, c_arm, transformed_points[0], transformed_points[8], 6)
    pygame.draw.line(surface, c_arm, transformed_points[1], transformed_points[9], 6)

    # Back Arms: 4->11, 5->10
    pygame.draw.line(surface, c_arm, transformed_points[4], transformed_points[11], 6)
    pygame.draw.line(surface, c_arm, transformed_points[5], transformed_points[10], 6)

    # Motors (circles)
    pygame.draw.circle(surface, (200, 50, 50), transformed_points[8], 7)  # FL Red
    pygame.draw.circle(surface, (200, 50, 50), transformed_points[9], 7)  # FR Red
    pygame.draw.circle(surface, (50, 200, 50), transformed_points[10], 7) # BL Green
    pygame.draw.circle(surface, (50, 200, 50), transformed_points[11], 7) # BR Green
    
    # Body 
    body_poly = [transformed_points[0], transformed_points[1], transformed_points[5], transformed_points[4]]
    pygame.draw.polygon(surface, (30, 100, 160), body_poly) 
    pygame.draw.polygon(surface, (200, 200, 200), body_poly, 1)

# Grid Rendering function
def draw_infinite_grid(surface, cam_x, cam_y, cam_z, yaw_angle):
    grid_size = 2000 
    spacing = 200   
    horizon = 1200  
    c = (60, 60, 80)
    
    world_yaw = math.radians(-yaw_angle)

    off_x = cam_x % spacing
    off_z = cam_z % spacing

    # Vertical Lines
    for i in range(-10, 11):
        lx = (i * spacing) - off_x
        lz_start = -200 
        rx1, rz1 = rotate_y(lx, lz_start, world_yaw)
        lz_end = horizon
        rx2, rz2 = rotate_y(lx, lz_end, world_yaw)
        
        p1 = project(rx1, cam_y, rz1 + 200) 
        p2 = project(rx2, cam_y, rz2 + 200)
        
        if p1[2] > 0 and p2[2] > 0: 
            pygame.draw.line(surface, c, (p1[0], p1[1]), (p2[0], p2[1]), 2)

    # Horizontal Lines
    for i in range(0, 15):
        lz = (i * spacing) - off_z
        if lz < -100: continue
        
        lx_left = -grid_size
        lx_right = grid_size
        rx1, rz1 = rotate_y(lx_left, lz, world_yaw)
        rx2, rz2 = rotate_y(lx_right, lz, world_yaw)
        
        p1 = project(rx1, cam_y, rz1 + 200)
        p2 = project(rx2, cam_y, rz2 + 200)
        
        if p1[2] > 0 and p2[2] > 0:
            pygame.draw.line(surface, c, (p1[0], p1[1]), (p2[0], p2[1]), 2)


# Main loop
mpu.mpu_setup_once()

try:
    while True:
        screen.fill((10, 10, 15)) 

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        # MPU Data
        roll, pitch, yaw = mpu.get_mpu_orientation()
        
        d_pitch = pitch if abs(pitch) > 3.0 else 0
        d_roll = roll if abs(roll) > 3.0 else 0

        # Basic physics
        vel_z += (-d_pitch * 0.1) 
        vel_x += (d_roll * 0.1)
        vel_z *= FRICTION
        vel_x *= FRICTION
        
        rad_yaw = math.radians(yaw)
        
        cam_x += vel_z * math.sin(rad_yaw) + vel_x * math.cos(rad_yaw)
        cam_z += vel_z * math.cos(rad_yaw) - vel_x * math.sin(rad_yaw)
        
        # Render grid and drone
        draw_infinite_grid(screen, cam_x, cam_y, cam_z, yaw)
        draw_drone(screen, roll, pitch, 0)

        # HUD drawing
        v_speed = math.hypot(vel_x, vel_z)
        hud_txt = font.render(f"POS: {int(cam_x)}, {int(cam_z)} | SPD: {v_speed:.1f}", True, (0, 255, 0))
        screen.blit(hud_txt, (10, HEIGHT - 30))
        
        title = font.render(f"R: {roll:.1f} P: {pitch:.1f} Y: {yaw:.1f}", True, (255, 255, 255))
        screen.blit(title, (10, 10))

        pygame.display.flip()
        clock.tick(60)

# Exit and cleanup
except KeyboardInterrupt:
    print("Exiting...")
    pygame.quit()
    sys.exit()