# Malik F (mhf68) & Hetao Y (hy668)
# 3D Free Roam with Title v5
# Added game states, GPIO 5 logic, environment graphics
# November 28, 2025

import pygame
import pigame
import math
import sys
import os
import time
import RPi.GPIO as GPIO

# Configuration
MONITOR_W, MONITOR_H = 800, 480
TFT_W, TFT_H = 320, 240
TFT_DEVICE = '/dev/fb1'
START_BTN_PIN = 5 # GPIO 5

# Speed Settings
SPEED_SCALAR = 0.4
ACCEL_FACTOR = 0.15 
FRICTION = 0.96     

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(START_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Display setup
os.putenv('SDL_VIDEODRIVER', 'fbcon')
os.putenv('SDL_FBDEV', '/dev/fb0') 
os.putenv('SDL_MOUSEDRV', 'dummy')
os.putenv('SDL_MOUSEDEV', '/dev/null')
os.putenv('DISPLAY', '')

pygame.init()
pygame.mouse.set_visible(False)
pitft = pigame.PiTft()

screen_hdmi = pygame.display.set_mode((MONITOR_W, MONITOR_H))
pygame.display.set_caption("Free Roam Mode")
screen_tft = pygame.Surface((TFT_W, TFT_H))

# Setup PiTFT Output
tft_file = None
try:
    tft_file = open(TFT_DEVICE, 'wb')
except IOError:
    pass 

import mpu6050_calibrate_v4 as mpu
mpu.mpu_setup_once()
clock = pygame.time.Clock()

# Fonts
font = pygame.font.SysFont("consolas", 18)
title_font = pygame.font.SysFont("consolas", 60, bold=True)
subtitle_font = pygame.font.SysFont("consolas", 30)
arrow_font = pygame.font.SysFont("consolas", 20, bold=True)
big_font = pygame.font.SysFont("consolas", 28, bold=True)

# 3D Math & Models
def rotate_y(x, z, angle_rad):
    c = math.cos(angle_rad); s = math.sin(angle_rad)
    return x*c - z*s, x*s + z*c

def rotate_3d(x, y, z, r, p, yw):
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

def project(x, y, z, cx, cy, fov):
    if z < 1: z = 1 
    scale = fov / (fov + z)
    return int(x * scale + cx), int(-y * scale + cy)

drone_verts = [
    (-10, -3, 15), (10, -3, 15), (10, 3, 15), (-10, 3, 15),
    (-10, -3, -15), (10, -3, -15), (10, 3, -15), (-10, 3, -15),
    (-30, 0, 30), (30, 0, 30), (30, 0, -30), (-30, 0, -30)
]

# Renderers
def render_title_screen():
    # Draw on HDMI
    screen_hdmi.fill((10, 10, 20))
    
    title_txt = title_font.render("FREE ROAM MODE", True, (255, 200, 50))
    sub_txt = subtitle_font.render("Press START Button to Begin", True, (200, 200, 200))
    
    tr = title_txt.get_rect(center=(MONITOR_W//2, MONITOR_H//2 - 40))
    sr = sub_txt.get_rect(center=(MONITOR_W//2, MONITOR_H//2 + 40))
    
    screen_hdmi.blit(title_txt, tr)
    screen_hdmi.blit(sub_txt, sr)
    
    # Draw on PiTFT (Simplified)
    screen_tft.fill((0, 0, 0))
    t_small = subtitle_font.render("READY", True, (0, 255, 0))
    tr_small = t_small.get_rect(center=(TFT_W//2, TFT_H//2))
    screen_tft.blit(t_small, tr_small)

    pygame.display.flip()
    if tft_file:
        tft_file.seek(0)
        tft_file.write(screen_tft.convert(16, 0).get_buffer())


def render_hdmi_game(surface, d_roll, d_pitch, d_yaw, cam_x, cam_z, v_speed):
    surface.fill((15, 15, 20))
    cx, cy = MONITOR_W // 2, MONITOR_H // 2
    fov = 500
    
    grid_size = 2000; spacing = 200; horizon = 1400 
    grid_color = (60, 60, 80)
    world_yaw = math.radians(-d_yaw)
    off_x = cam_x % spacing; off_z = cam_z % spacing
    
    # Z-Lines
    for i in range(-12, 13):
        lx = (i * spacing) - off_x
        rx1, rz1 = rotate_y(lx, -200, world_yaw)   
        rx2, rz2 = rotate_y(lx, horizon, world_yaw)
        p1 = project(rx1, -100, rz1 + 200, cx, cy, fov)
        p2 = project(rx2, -100, rz2 + 200, cx, cy, fov)
        if (rz1 + 200) > 1 and (rz2 + 200) > 1:
            pygame.draw.line(surface, grid_color, p1, p2, 1)

    # X-Lines
    for i in range(0, 15):
        lz = (i * spacing) - off_z
        if lz < -100: continue 
        rx1, rz1 = rotate_y(-grid_size, lz, world_yaw)
        rx2, rz2 = rotate_y(grid_size, lz, world_yaw)
        p1 = project(rx1, -100, rz1 + 200, cx, cy, fov)
        p2 = project(rx2, -100, rz2 + 200, cx, cy, fov)
        if (rz1 + 200) > 1 and (rz2 + 200) > 1:
            pygame.draw.line(surface, grid_color, p1, p2, 1)

    # Solid Drone
    r_rad = math.radians(d_roll); p_rad = math.radians(d_pitch)
    drone_pts = []
    for v in drone_verts:
        x, y, z = v
        x, y, z = rotate_3d(x, y, z, -r_rad, p_rad, 0)
        z += 180; y += 20
        drone_pts.append(project(x, y, z, cx, cy, fov))

    # Draw Drone 
    c_arm = (80, 80, 80)
    pygame.draw.line(surface, c_arm, drone_pts[0], drone_pts[8], 6)
    pygame.draw.line(surface, c_arm, drone_pts[1], drone_pts[9], 6)
    pygame.draw.line(surface, c_arm, drone_pts[4], drone_pts[11], 6)
    pygame.draw.line(surface, c_arm, drone_pts[5], drone_pts[10], 6)
    pygame.draw.circle(surface, (200, 50, 50), drone_pts[8], 8)
    pygame.draw.circle(surface, (200, 50, 50), drone_pts[9], 8)
    pygame.draw.circle(surface, (50, 200, 50), drone_pts[10], 8)
    pygame.draw.circle(surface, (50, 200, 50), drone_pts[11], 8)
    body_poly = [drone_pts[0], drone_pts[1], drone_pts[5], drone_pts[4]]
    pygame.draw.polygon(surface, (30, 100, 160), body_poly) 
    pygame.draw.polygon(surface, (200, 200, 200), body_poly, 1) 

    # HUD
    info = font.render(f"POS: {int(cam_x)}, {int(cam_z)} | SPEED: {int(v_speed*10)}", True, (0, 255, 0))
    surface.blit(info, (20, MONITOR_H - 40))

# Cockpit Render Function
def render_cockpit_game(surface, d_roll, d_pitch, d_yaw):
    surface.fill((0, 0, 0))
    cx, cy = TFT_W // 2, TFT_H // 2
    
    input_forward = d_pitch 
    input_strafe = d_roll
    mag = math.hypot(input_forward, input_strafe)
    
    if mag > 3.0: 
        angle = math.atan2(input_strafe, input_forward) 
        arrow_len = min(60, mag * 5)
        tip_x = cx + math.sin(angle) * arrow_len
        tip_y = cy - math.cos(angle) * arrow_len
        
        pygame.draw.line(surface, (0, 255, 0), (cx, cy), (tip_x, tip_y), 6)
        pygame.draw.circle(surface, (0, 255, 0), (cx, cy), 8)
        
        head_size = 15
        p1 = (tip_x + math.sin(angle + 2.6)*head_size, tip_y - math.cos(angle + 2.6)*head_size)
        p2 = (tip_x + math.sin(angle - 2.6)*head_size, tip_y - math.cos(angle - 2.6)*head_size)
        pygame.draw.polygon(surface, (0, 255, 0), [(tip_x, tip_y), p1, p2])
    else:
        pygame.draw.circle(surface, (50, 50, 50), (cx, cy), 10)
        pygame.draw.circle(surface, (100, 100, 100), (cx, cy), 10, 2)

    status_text = "HOVERING"
    if mag > 3.0:
        dirs = []
        if input_forward > 3: dirs.append("FORWARD")
        elif input_forward < -3: dirs.append("BACKWARD")
        if input_strafe > 3: dirs.append("RIGHT")
        elif input_strafe < -3: dirs.append("LEFT")
        if dirs: status_text = "-".join(dirs)
    
    txt_surf = big_font.render(f"{status_text}", True, (255, 255, 255))
    txt_rect = txt_surf.get_rect(center=(cx, TFT_H - 30))
    surface.blit(txt_surf, txt_rect)
    
    surface.blit(arrow_font.render(f"P: {d_pitch:.0f}", True, (150, 150, 150)), (10, 10))
    surface.blit(arrow_font.render(f"R: {d_roll:.0f}", True, (150, 150, 150)), (10, 35))
    surface.blit(arrow_font.render(f"Y: {d_yaw:.0f}°", True, (50, 200, 255)), (TFT_W - 90, 10))


# Main Logic
game_state = "TITLE"
cam_x, cam_y, cam_z = 0.0, -100.0, 0.0
global_vx = 0.0
global_vz = 0.0

try:
    while True:
        # Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                GPIO.cleanup()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    GPIO.cleanup()
                    sys.exit()

        # State Machine
        if game_state == "TITLE":
            render_title_screen()
            
            # Check GPIO Button
            if GPIO.input(START_BTN_PIN) == GPIO.LOW:
                game_state = "PLAYING"
                time.sleep(0.5) # Debounce

        elif game_state == "PLAYING":
            # Sensors
            roll, pitch, yaw = mpu.get_mpu_orientation()
            dz_roll = roll if abs(roll) > 2 else 0
            dz_pitch = pitch if abs(pitch) > 2 else 0

            # Physics
            accel_fwd = (dz_pitch * ACCEL_FACTOR) * SPEED_SCALAR
            accel_side = (dz_roll * ACCEL_FACTOR) * SPEED_SCALAR
            
            rad_yaw = math.radians(yaw)
            global_acc_x = accel_fwd * math.sin(rad_yaw) + accel_side * math.cos(rad_yaw)
            global_acc_z = accel_fwd * math.cos(rad_yaw) - accel_side * math.sin(rad_yaw)
            
            global_vx += global_acc_x
            global_vz += global_acc_z
            global_vx *= FRICTION
            global_vz *= FRICTION
            
            cam_x += global_vx
            cam_z += global_vz

            # Render
            render_hdmi_game(screen_hdmi, roll, pitch, yaw, cam_x, cam_z, math.hypot(global_vx, global_vz))
            render_cockpit_game(screen_tft, roll, pitch, yaw)
            
            pygame.display.flip() 
            if tft_file:
                tft_file.seek(0)
                tft_file.write(screen_tft.convert(16, 0).get_buffer())

        clock.tick(30)

except KeyboardInterrupt:
    if tft_file: tft_file.close()
    GPIO.cleanup()
    pygame.quit()
    sys.exit()