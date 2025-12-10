# Malik F (mhf68) & Hetao Y (hy668)
# pygame3D v4
# Added better movement physics (momentum and drift), rotation matrix for global thrust (scaling speed)
# Removed simplified physics.
# November 25, 2025

import pygame
import pigame
import math
import sys
import os

# Initial functions to have second monitor display
MONITOR_W, MONITOR_H = 800, 480
TFT_W, TFT_H = 320, 240
TFT_DEVICE = '/dev/fb1'

# Speed multiplier (can slow or speed up)
SPEED_SCALAR = 0.4
ACCEL_FACTOR = 0.15 
FRICTION = 0.96

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
pygame.display.set_caption("Drone 3D Physics V5")
screen_tft = pygame.Surface((TFT_W, TFT_H))

# Setup PiTFT Output (AI helped with understanding/using this method)
tft_file = None
try:
    tft_file = open(TFT_DEVICE, 'wb')
except IOError:
    pass 

# Import calibration file
import mpu6050_calibrate_v4 as mpu
mpu.mpu_setup_once()
clock = pygame.time.Clock()

# Main fonts
font = pygame.font.SysFont("consolas", 18)

# For cockpit
big_font = pygame.font.SysFont("consolas", 28, bold=True)
arrow_font = pygame.font.SysFont("consolas", 20, bold=True)

# Rotate functions
def rotate_y(x, z, angle_rad):
    # Rotates a point around Y axis (Yaw)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    rx = x * cos_a - z * sin_a
    rz = x * sin_a + z * cos_a
    return rx, rz

# Rotate functions for models.
def rotate_3d(x, y, z, r, p, yw):
    # Combined rotation for models
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

# Projection function
def project(x, y, z, cx, cy, fov):
    if z < 1: z = 1 
    scale = fov / (fov + z)
    return int(x * scale + cx), int(-y * scale + cy)

# Copied from previous
drone_verts = [
    (-10, -3, 15), (10, -3, 15), (10, 3, 15), (-10, 3, 15), # Front
    (-10, -3, -15), (10, -3, -15), (10, 3, -15), (-10, 3, -15), # Back
    (-30, 0, 30), (30, 0, 30), (30, 0, -30), (-30, 0, -30) # Arms tip
]

# Camera state variables
cam_x = 0.0
cam_y = -100.0 
cam_z = 0.0

# Velocity
global_vx = 0.0
global_vz = 0.0

# Function to render on monitor
def render_hdmi(surface, d_roll, d_pitch, d_yaw, cam_x, cam_z):
    surface.fill((15, 15, 20))
    
    cx, cy = MONITOR_W // 2, MONITOR_H // 2
    fov = 500
    
    # Grid drawing
    grid_size = 2000 
    spacing = 200 
    horizon = 1400 
    grid_color = (60, 60, 80)
    
    # Rotating world view
    world_yaw = math.radians(-d_yaw)
    
    off_x = cam_x % spacing
    off_z = cam_z % spacing
    
    # Y-Axis Lines
    for i in range(-12, 13):
        lx = (i * spacing) - off_x
        rx1, rz1 = rotate_y(lx, -200, world_yaw)   
        rx2, rz2 = rotate_y(lx, horizon, world_yaw)
        
        p1 = project(rx1, cam_y, rz1 + 200, cx, cy, fov)
        p2 = project(rx2, cam_y, rz2 + 200, cx, cy, fov)
        
        if (rz1 + 200) > 1 and (rz2 + 200) > 1:
            pygame.draw.line(surface, grid_color, p1, p2, 1)

    # X-Axis Lines
    for i in range(0, 15):
        lz = (i * spacing) - off_z
        if lz < -100: continue 
        
        rx1, rz1 = rotate_y(-grid_size, lz, world_yaw)
        rx2, rz2 = rotate_y(grid_size, lz, world_yaw)
        
        p1 = project(rx1, cam_y, rz1 + 200, cx, cy, fov)
        p2 = project(rx2, cam_y, rz2 + 200, cx, cy, fov)
        
        if (rz1 + 200) > 1 and (rz2 + 200) > 1:
            pygame.draw.line(surface, grid_color, p1, p2, 1)

    # Draw drone
    model_offset_z = 180 
    model_offset_y = 20
    
    r_rad = math.radians(d_roll)
    p_rad = math.radians(d_pitch)
    
    drone_pts = []
    for v in drone_verts:
        x, y, z = v
        # Apply Tilt
        x, y, z = rotate_3d(x, y, z, -r_rad, p_rad, 0)
        
        # Position in front of camera
        z += model_offset_z
        y += model_offset_y
        
        drone_pts.append(project(x, y, z, cx, cy, fov))

      
    # Arms main
    c_arm = (80, 80, 80)
    pygame.draw.line(surface, c_arm, drone_pts[0], drone_pts[8], 6)
    pygame.draw.line(surface, c_arm, drone_pts[1], drone_pts[9], 6)
    # Back Arms
    pygame.draw.line(surface, c_arm, drone_pts[4], drone_pts[11], 6)
    pygame.draw.line(surface, c_arm, drone_pts[5], drone_pts[10], 6)
    
    # Draw motors (circles)
    pygame.draw.circle(surface, (200, 50, 50), drone_pts[8], 8)  # FL Red
    pygame.draw.circle(surface, (200, 50, 50), drone_pts[9], 8)  # FR Red
    pygame.draw.circle(surface, (50, 200, 50), drone_pts[10], 8) # BL Green
    pygame.draw.circle(surface, (50, 200, 50), drone_pts[11], 8) # BR Green
    
    # Draw Body
    body_poly = [drone_pts[0], drone_pts[1], drone_pts[5], drone_pts[4]]
    pygame.draw.polygon(surface, (30, 100, 160), body_poly) 
    pygame.draw.polygon(surface, (200, 200, 200), body_poly, 1) 

    # HUD Drawing
    v_speed = math.hypot(global_vx, global_vz) * 10 
    info = font.render(f"POS: {int(cam_x)}, {int(cam_z)} | SPEED: {int(v_speed)}", True, (0, 255, 0))
    surface.blit(info, (20, MONITOR_H - 40))


# Rendering for cockpit arrow
def render_cockpit(surface, d_roll, d_pitch, d_yaw):
    surface.fill((0, 0, 0))
    cx, cy = TFT_W // 2, TFT_H // 2
    
    # Map pitch and roll with arrow
    input_forward = d_pitch 
    input_strafe = d_roll
    
    # Magnitude check
    mag = math.hypot(input_forward, input_strafe)
    
    # Draw arrow center (3.0 for deadzone)
    if mag > 3.0: 
        angle = math.atan2(input_strafe, input_forward) # -y for screen up
        
        # Length of arrow
        arrow_len = min(60, mag * 5)
        
        # Calculate arrow tip
        tip_x = cx + math.sin(angle) * arrow_len
        tip_y = cy - math.cos(angle) * arrow_len
        
        # Draw Arrow body
        pygame.draw.line(surface, (0, 255, 0), (cx, cy), (tip_x, tip_y), 6)
        pygame.draw.circle(surface, (0, 255, 0), (cx, cy), 8)
        
        # Draw Arrow Head
        head_size = 15
        head_ang_1 = angle + math.radians(150)
        head_ang_2 = angle - math.radians(150)
        
        p1 = (tip_x + math.sin(head_ang_1)*head_size, tip_y - math.cos(head_ang_1)*head_size)
        p2 = (tip_x + math.sin(head_ang_2)*head_size, tip_y - math.cos(head_ang_2)*head_size)
        
        pygame.draw.polygon(surface, (0, 255, 0), [(tip_x, tip_y), p1, p2])
    else:
        # Draw Neutral Dot
        pygame.draw.circle(surface, (50, 50, 50), (cx, cy), 10)
        pygame.draw.circle(surface, (100, 100, 100), (cx, cy), 10, 2)

    # Status of arrow (movement)
    status_text = "HOVERING"
    if mag > 3.0:
        dirs = []
        if input_forward > 3: dirs.append("FORWARD")
        elif input_forward < -3: dirs.append("BACKWARD")
        
        if input_strafe > 3: dirs.append("RIGHT")
        elif input_strafe < -3: dirs.append("LEFT")
        
        if dirs:
            status_text = "-".join(dirs)
    
    # Render Text
    txt_surf = big_font.render(f"{status_text}", True, (255, 255, 255))
    txt_rect = txt_surf.get_rect(center=(cx, TFT_H - 30))
    surface.blit(txt_surf, txt_rect)
    
    # HUD Data
    surface.blit(arrow_font.render(f"P: {d_pitch:.0f}", True, (150, 150, 150)), (10, 10))
    surface.blit(arrow_font.render(f"R: {d_roll:.0f}", True, (150, 150, 150)), (10, 35))
    
    surface.blit(arrow_font.render(f"Y: {d_yaw:.0f}°", True, (50, 200, 255)), (TFT_W - 90, 10))


# Main Loop
try:
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()

        # MPU Data
        roll, pitch, yaw = mpu.get_mpu_orientation()
        
        dz_roll = roll if abs(roll) > 2 else 0
        dz_pitch = pitch if abs(pitch) > 2 else 0

        # Basic Physics
        accel_fwd = (dz_pitch * ACCEL_FACTOR) * SPEED_SCALAR
        accel_side = (dz_roll * ACCEL_FACTOR) * SPEED_SCALAR
        
        # Calculate movement based on Yaw
        rad_yaw = math.radians(yaw)
        
        global_acc_x = accel_fwd * math.sin(rad_yaw) + accel_side * math.cos(rad_yaw)
        global_acc_z = accel_fwd * math.cos(rad_yaw) - accel_side * math.sin(rad_yaw)
        
        global_vx += global_acc_x
        global_vz += global_acc_z
        
        # Friction
        global_vx *= FRICTION
        global_vz *= FRICTION
        
        cam_x += global_vx
        cam_z += global_vz

        # Render both modes
        render_hdmi(screen_hdmi, roll, pitch, yaw, cam_x, cam_z)
        render_cockpit(screen_tft, roll, pitch, yaw)
        
        pygame.display.flip() 
        
        if tft_file:
            tft_file.seek(0)
            tft_file.write(screen_tft.convert(16, 0).get_buffer())

        clock.tick(30)

# Exit anad cleanup
except KeyboardInterrupt:
    if tft_file: tft_file.close()
    pygame.quit()
    sys.exit()