# Malik F (mhf68) & Hetao Y (hy668)
# Drone 3D Free Roam (WIP) v2
# Added game_wrap function. This means commenting out initializations, and letting our main file call these functions.
# December 5, 2025

import pygame
import pigame
import math
import sys
import os
import time
import random
import RPi.GPIO as GPIO
import mpu6050_calibrate_v4 as mpu

# Display Initialize
MONITOR_W, MONITOR_H = 800, 480
TFT_W, TFT_H = 320, 240
TFT_DEVICE = '/dev/fb1'
START_BTN_PIN = 5 # GPIO 5
RESTART_BTN_PIN = 6 # GPIO 6

# Movement speed variables
SPEED_SCALAR = 0.4
ACCEL_FACTOR = 0.15 
FRICTION = 0.96     

# GPIO setup
# GPIO.setmode(GPIO.BCM)
# GPIO.setup(START_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
# GPIO.setup(RESTART_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Display setup for Main Screen (fb0)
# os.putenv('SDL_VIDEODRIVER', 'fbcon')
# os.putenv('SDL_FBDEV', '/dev/fb0') 
# os.putenv('SDL_MOUSEDRV', 'dummy')
# os.putenv('SDL_MOUSEDEV', '/dev/null')
# os.putenv('DISPLAY', '')

# pygame.init()
# pygame.mouse.set_visible(False)
# pitft = pigame.PiTft()

# screen_hdmi = pygame.display.set_mode((MONITOR_W, MONITOR_H))
# pygame.display.set_caption("FreeRoam Mode")
# screen_tft = pygame.Surface((TFT_W, TFT_H))

# Setup piTFT manually (fb1)
# tft_file = None
# try:
#     tft_file = open(TFT_DEVICE, 'wb')
# except IOError:
#     pass 
# mpu.mpu_setup_once()
# clock = pygame.time.Clock()

# Monitor fonts
# font = pygame.font.SysFont("consolas", 18)
# title_font = pygame.font.SysFont("consolas", 50, bold=True)
# subtitle_font = pygame.font.SysFont("consolas", 30)
font = None
title_font = None
subtitle_font = None

# piTFT fonts
# arrow_font = pygame.font.SysFont("consolas", 20, bold=True)
# big_font = pygame.font.SysFont("consolas", 28, bold=True)
arrow_font = None
big_font = None

# 3D math helper functions
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

# Convert 3D coordinates to 2D screen points
def project(x, y, z, cx, cy, fov):
    if z < 1: z = 1 
    scale = fov / (fov + z)
    return int(x * scale + cx), int(-y * scale + cy)

# Define 3D drone model vertices
drone_verts = [(-10, -3, 15), (10, -3, 15), (10, 3, 15), (-10, 3, 15),(-10, -3, -15), (10, -3, -15), (10, 3, -15), (-10, 3, -15),
               (-30, 0, 30), (30, 0, 30), (30, 0, -30), (-30, 0, -30)]

# Generate random grass patches
grass_patches = []
for _ in range(80):
    grass_patches.append((random.randint(-1500, 1500), random.randint(-1500, 1500)))

# Static cloud positions
clouds = [(150, 50, 60), (450, 80, 80), (700, 40, 70), (50, 90, 50)]

# Draw the main menu and waiting text
def render_title_screen(screen_hdmi, screen_tft, tft_file):
    screen_hdmi.fill((10, 10, 20))
    
    # Title
    if title_font and subtitle_font:
        title_txt = title_font.render("Palm Pilot: 3D Free Roam (WIP)", True, (80, 160, 255))
        sub_txt = subtitle_font.render("Press START Button", True, (200, 200, 200))
        
        tr = title_txt.get_rect(center=(MONITOR_W//2, MONITOR_H//2 - 40))
        sr = sub_txt.get_rect(center=(MONITOR_W//2, MONITOR_H//2 + 40))
        
        screen_hdmi.blit(title_txt, tr)
        screen_hdmi.blit(sub_txt, sr)
    
    screen_tft.fill((0, 0, 0))
    if subtitle_font:
        t_small = subtitle_font.render("WAITING", True, (50, 50, 50))
        tr_small = t_small.get_rect(center=(TFT_W//2, TFT_H//2))
        screen_tft.blit(t_small, tr_small)

    pygame.display.flip()
    if tft_file:
        tft_file.seek(0)
        tft_file.write(screen_tft.convert(16, 0).get_buffer())


# Render the 3D world and drone
def render_hdmi_game(surface, d_roll, d_pitch, d_yaw, cam_x, cam_z, v_speed):
    # Calculate horizon line based on pitch
    horizon_y = (MONITOR_H // 2) + int(d_pitch * 5)
    
    # Draw sky and ground
    surface.fill((135, 206, 235), (0, 0, MONITOR_W, horizon_y)) 
    # Ground
    surface.fill((34, 100, 34), (0, horizon_y, MONITOR_W, MONITOR_H - horizon_y)) 

    cx, cy = MONITOR_W // 2, MONITOR_H // 2
    fov = 500
    
    # Draw static background elements
    
    # Sun drawing
    pygame.draw.circle(surface, (255, 255, 0), (650, horizon_y - 150), 40)

    # Clouds drawing
    for c_x, c_y_off, size in clouds:
        pygame.draw.ellipse(surface, (240, 240, 255), (c_x, horizon_y - 100 - c_y_off, size*2, size))

    # Mountain drawing
    mnt_color = (60, 80, 100)
    pts = [
        (0, horizon_y), 
        (200, horizon_y - 100), 
        (400, horizon_y - 50), 
        (600, horizon_y - 150),
        (800, horizon_y)
    ]
    pygame.draw.polygon(surface, mnt_color, pts)

    # Draw moving grass on ground
    world_yaw = math.radians(-d_yaw)
    grid_size = 3000
    
    for gx, gz in grass_patches:
        rel_x = (gx - cam_x) % grid_size - (grid_size // 2)
        rel_z = (gz - cam_z) % grid_size - (grid_size // 2)
        
        if rel_z < 10: rel_z += grid_size
        
        rx, rz = rotate_y(rel_x, rel_z, world_yaw)
        
        if rz > 10:
            px, py = project(rx, -150, rz, cx, cy, fov)
            
            if 0 < px < MONITOR_W and py > horizon_y:
                g_height = int(800 / rz)
                if g_height > 0:
                    pygame.draw.line(surface, (50, 200, 50), (px, py), (px, py - g_height), 2)


    # Rotate and project drone vertices
    r_rad = math.radians(d_roll); p_rad = math.radians(d_pitch)
    
    drone_pts = []
    for v in drone_verts:
        x, y, z = v
        x, y, z = rotate_3d(x, y, z, -r_rad, p_rad, 0)
        # Original projection logic
        drone_pts.append(project(x, y + 20, z + 180, cx, cy, fov))

    # Connect vertices to draw drone frame
    c_arm = (80, 80, 80)
    # Arms
    pygame.draw.line(surface, c_arm, drone_pts[0], drone_pts[8], 6)
    pygame.draw.line(surface, c_arm, drone_pts[1], drone_pts[9], 6)
    pygame.draw.line(surface, c_arm, drone_pts[4], drone_pts[11], 6)
    pygame.draw.line(surface, c_arm, drone_pts[5], drone_pts[10], 6)
    
    # Motors
    pygame.draw.circle(surface, (200, 50, 50), drone_pts[8], 8)
    pygame.draw.circle(surface, (200, 50, 50), drone_pts[9], 8)
    pygame.draw.circle(surface, (50, 200, 50), drone_pts[10], 8)
    pygame.draw.circle(surface, (50, 200, 50), drone_pts[11], 8)
    
    # Body
    body_poly = [drone_pts[0], drone_pts[1], drone_pts[5], drone_pts[4]]
    pygame.draw.polygon(surface, (30, 100, 160), body_poly) 
    pygame.draw.polygon(surface, (200, 200, 200), body_poly, 1) 


# Cockpit generate function for piTFT
def render_cockpit_game(surface, d_roll, d_pitch, d_yaw):
    surface.fill((0, 0, 0))
    cx, cy = TFT_W // 2, TFT_H // 2
    
    # Map mpu inputs with movement
    input_forward = d_pitch 
    input_strafe = d_roll
    mag = math.hypot(input_forward, input_strafe)
    
    # Check if movement is greater than deadzone
    if mag > 3.0: 
        angle = math.atan2(input_strafe, input_forward) 
        arrow_len = min(60, mag * 5)
        tip_x = cx + math.sin(angle) * arrow_len
        tip_y = cy - math.cos(angle) * arrow_len
        
        # Draw the direction arrow
        pygame.draw.line(surface, (0, 255, 0), (cx, cy), (tip_x, tip_y), 6)
        pygame.draw.circle(surface, (0, 255, 0), (cx, cy), 8)
        
        # Draw the arrow tip
        head_size = 15
        p1 = (tip_x + math.sin(angle + 2.6)*head_size, tip_y - math.cos(angle + 2.6)*head_size)
        p2 = (tip_x + math.sin(angle - 2.6)*head_size, tip_y - math.cos(angle - 2.6)*head_size)
        pygame.draw.polygon(surface, (0, 255, 0), [(tip_x, tip_y), p1, p2])
    else:
        # Draw center circle when not moving
        pygame.draw.circle(surface, (50, 50, 50), (cx, cy), 10)
        pygame.draw.circle(surface, (100, 100, 100), (cx, cy), 10, 2)

    # Determine text status based on input
    status_text = "HOVERING"
    if mag > 3.0:
        dirs = []
        if input_forward > 3: dirs.append("FORWARD")
        elif input_forward < -3: dirs.append("BACKWARD")
        if input_strafe > 3: dirs.append("RIGHT")
        elif input_strafe < -3: dirs.append("LEFT")
        if dirs: status_text = "-".join(dirs)
    
    # Display text on screen
    if big_font:
        txt_surf = big_font.render(f"{status_text}", True, (255, 255, 255))
        txt_rect = txt_surf.get_rect(center=(cx, TFT_H - 30))
        surface.blit(txt_surf, txt_rect)
    
    # Show raw values on display
    if arrow_font:
        surface.blit(arrow_font.render(f"P: {d_pitch:.0f}", True, (150, 150, 150)), (10, 10))
        surface.blit(arrow_font.render(f"R: {d_roll:.0f}", True, (150, 150, 150)), (10, 35))
        surface.blit(arrow_font.render(f"Y: {d_yaw:.0f}°", True, (50, 200, 255)), (TFT_W - 90, 10))


# WRAPPER FUNCTION
def run_game(main_screen, main_pitft):
    global game_state, cam_x, cam_y, cam_z, global_vx, global_vz, menu_hold_timer
    global font, title_font, subtitle_font, arrow_font, big_font
    
    # Use passed in surfaces
    screen_hdmi = main_screen
    pitft = main_pitft
    
    # Init Local Resources
    font = pygame.font.SysFont("consolas", 18)
    title_font = pygame.font.SysFont("consolas", 50, bold=True)
    subtitle_font = pygame.font.SysFont("consolas", 30)
    arrow_font = pygame.font.SysFont("consolas", 20, bold=True)
    big_font = pygame.font.SysFont("consolas", 28, bold=True)

    tft_file = None
    try:
        tft_file = open(TFT_DEVICE, 'wb')
    except IOError:
        pass
    
    screen_tft = pygame.Surface((TFT_W, TFT_H))
    clock = pygame.time.Clock()
    
    mpu.mpu_setup_once()

    # Reset vars
    game_state = "TITLE"
    cam_x, cam_y, cam_z = 0.0, -100.0, 0.0
    global_vx = 0.0
    global_vz = 0.0
    menu_hold_timer = 0
    running = True

    try:
        while running:
            # Event handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
        
            # Return to title screen if both buttons pressed
            if GPIO.input(START_BTN_PIN) == GPIO.HIGH and GPIO.input(RESTART_BTN_PIN) == GPIO.HIGH:
                game_state = "TITLE"

                # Stop movement when returning to title
                global_vx, global_vz = 0.0, 0.0
                time.sleep(0.5) 

            # Hold blue button to return to Quit
            if GPIO.input(START_BTN_PIN) == GPIO.HIGH:
                if menu_hold_timer == 0:
                    menu_hold_timer = time.time()
                elif time.time() - menu_hold_timer > 2.0:
                    print("Quitting Game")
                    running = False
            else:
                menu_hold_timer = 0

            # Title screen state
            if game_state == "TITLE":
                render_title_screen(screen_hdmi, screen_tft, tft_file)
                
                # Start Game (Blue Button Only)
                if GPIO.input(START_BTN_PIN) == GPIO.HIGH and GPIO.input(RESTART_BTN_PIN) == GPIO.LOW:
                    game_state = "PLAYING"
                    time.sleep(0.5) 

            # Playing state
            elif game_state == "PLAYING":
                # Update sensor readings
                roll, pitch, yaw = mpu.get_mpu_orientation()
                dz_roll = roll if abs(roll) > 2 else 0
                dz_pitch = pitch if abs(pitch) > 2 else 0

                # Physics and acceleration based on mpu input
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

                # Render 3D world and cockpit
                render_hdmi_game(screen_hdmi, roll, pitch, yaw, cam_x, cam_z, math.hypot(global_vx, global_vz))
                render_cockpit_game(screen_tft, roll, pitch, yaw)
                
                pygame.display.flip() 
                if tft_file:
                    tft_file.seek(0)
                    tft_file.write(screen_tft.convert(16, 0).get_buffer())
                
                # Reset position when yellow button is pressed
                if GPIO.input(RESTART_BTN_PIN) == GPIO.HIGH and GPIO.input(START_BTN_PIN) == GPIO.LOW:
                    cam_x, cam_z = 0.0, 0.0
                    global_vx, global_vz = 0.0, 0.0
                    print("Position Reset!")
                    time.sleep(0.2)

            clock.tick(30)

    # exit and cleanup
    except KeyboardInterrupt:
        pass
    finally:
        if tft_file: tft_file.close()
        # GPIO.cleanup()
        # pygame.quit()
        # sys.exit()
        return