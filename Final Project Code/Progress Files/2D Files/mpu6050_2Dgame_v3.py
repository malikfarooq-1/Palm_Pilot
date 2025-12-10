# Malik F (mhf68) & Hetao Y (hy668)
# Added more physics (velocity, acceleration, friction), animated propellers, background grid v3
# Removed direct mapping from sensor.
# November 21, 2025

import pygame
import pigame
import math
import time
import os
import sys

# PiTFT display variables
os.putenv('SDL_VIDEODRIVER', 'fbcon')
os.putenv('SDL_FBDEV', '/dev/fb0') 
os.putenv('SDL_MOUSEDRV', 'dummy')
os.putenv('SDL_MOUSEDEV', '/dev/null')
os.putenv('DISPLAY', '')

pygame.init()
pygame.mouse.set_visible(False)
pitft = pigame.PiTft()

# Import the optimized MPU script
import mpu6050_calibrate_v4 as mpu  

# Screen resolution 
WIDTH, HEIGHT = 800, 480
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Drone Controlled by MPU6050")

clock = pygame.time.Clock()

# Drone state
x = WIDTH // 2
y = HEIGHT // 2
vx = 0  # Velocity X
vy = 0  # Velocity Y

# Initialized variables for better physics 
ACCEL_FACTOR = 0.08    # How fast it speeds up
FRICTION = 0.95        # How fast it slows down (0.0 - 1.0)
MAX_SPEED = 8.0        # Max speed
DEADZONE = 3.0         # Prevents drift when flat

# Speed Multiplier (Lower = Slower)
SPEED_SCALAR = 0.4     

font = pygame.font.SysFont("consolas", 22)

# Function to draw better looking drone
def draw_polished_drone(surface, cx, cy, angle, frame_count):
    rad = math.radians(angle)
    
    # Help to rotate points around the center (cx, cy)
    def rot(px, py):
        rx = px * math.cos(rad) - py * math.sin(rad)
        ry = px * math.sin(rad) + py * math.cos(rad)
        return (cx + rx, cy + ry)

    # Arms in a cross formation
    pygame.draw.line(surface, (50, 50, 50), rot(-45, -45), rot(45, 45), 8)
    pygame.draw.line(surface, (50, 50, 50), rot(-45, 45), rot(45, -45), 8)

    # Manipulate circles for movement on propellers.
    prop_offset = (frame_count % 3) * 2
    
    # Motor positions
    motors = [(-45, -45), (45, -45), (45, 45), (-45, 45)] # FL, FR, BR, BL
    
    for i, (mx, my) in enumerate(motors):
        m_screen = rot(mx, my)
        
        # Draw Motor Housing
        pygame.draw.circle(surface, (30, 30, 30), (int(m_screen[0]), int(m_screen[1])), 8)
        
        # Draw Spinning Blade (Blur)
        pygame.draw.circle(surface, (255, 255, 255), (int(m_screen[0]), int(m_screen[1])), 18 + prop_offset, 2)
        pygame.draw.circle(surface, (200, 200, 200), (int(m_screen[0]), int(m_screen[1])), 10, 1)

        # Red for front, green for back (LED)
        if i < 2: 
            led_color = (255, 50, 50) # Red
        else:
            led_color = (50, 255, 50) # Green
            
        pygame.draw.circle(surface, led_color, (int(m_screen[0]), int(m_screen[1])), 4)

    # Main body
    body_points = [
        rot(0, -25),  # Front
        rot(15, 10),  # Right
        rot(0, 20),   # Back
        rot(-15, 10)  # Left
    ]
    pygame.draw.polygon(surface, (20, 20, 20), body_points)       # Black outline
    pygame.draw.polygon(surface, (80, 100, 140), body_points, 0)  # Body color


# Function to draw HUD
def draw_hud(surface, roll, pitch, yaw, vx, vy):
    
    # Background box
    s = pygame.Surface((220, 110))
    s.set_alpha(150)
    s.fill((0, 0, 0))
    surface.blit(s, (5, 5))

    col = (255, 255, 255)
    
    # Indicate which values are active (green if moving)
    r_col = (50, 255, 50) if abs(roll) > DEADZONE else col
    p_col = (50, 255, 50) if abs(pitch) > DEADZONE else col

    text1 = font.render(f"Roll : {roll:6.1f}°", True, r_col)
    text2 = font.render(f"Pitch: {pitch:6.1f}°", True, p_col)
    text3 = font.render(f"Yaw  : {yaw:6.1f}°", True, col)
    text4 = font.render(f"Speed: {math.hypot(vx, vy):.1f}", True, (200, 200, 255))

    surface.blit(text1, (10, 10))
    surface.blit(text2, (10, 35))
    surface.blit(text3, (10, 60))
    surface.blit(text4, (10, 85))

# Main loop
mpu.mpu_setup_once() # From calibration
frame_count = 0

running = True
try:
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            # ESC to quit
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        # Read mpu data
        roll, pitch, yaw = mpu.get_mpu_orientation()
        yaw = -yaw 

        # Physics Upgraded
        
        # Add Deadzone for stability
        eff_pitch = pitch if abs(pitch) > DEADZONE else 0
        eff_roll  = roll  if abs(roll)  > DEADZONE else 0

        # Calculate Thrust vectors based on Pitch/Roll, can use speed multiplier
        thrust_forward = (eff_pitch * ACCEL_FACTOR) * SPEED_SCALAR
        thrust_strafe  = (eff_roll  * ACCEL_FACTOR) * SPEED_SCALAR

        # yaw determines forward side
        rad_yaw = math.radians(yaw)

        # Standard rotation matrix
        acc_x = thrust_forward * math.sin(rad_yaw) + thrust_strafe * math.cos(rad_yaw)
        acc_y = thrust_forward * -math.cos(rad_yaw) + thrust_strafe * math.sin(rad_yaw)

        # Update Velocity
        vx += acc_x
        vy += acc_y

        # Apply Friction (Air Resistance)
        vx *= FRICTION
        vy *= FRICTION

        # Update Position
        x += vx
        y += vy

        # Screen Bounds (Bounce effect)
        if x < 0: x = 0; vx = -vx * 0.5
        if x > WIDTH: x = WIDTH; vx = -vx * 0.5
        if y < 0: y = 0; vy = -vy * 0.5
        if y > HEIGHT: y = HEIGHT; vy = -vy * 0.5

        # Drawing screen
        screen.fill((30, 30, 35))
        
        # Grid variables
        grid_spacing = 50
        offset_x = int(x) % grid_spacing
        offset_y = int(y) % grid_spacing
        
        # Drawing grid (for visuals)
        # Vertical lines
        for i in range(-grid_spacing, WIDTH + grid_spacing, grid_spacing):
            line_x = i - offset_x
            pygame.draw.line(screen, (50, 50, 60), (line_x, 0), (line_x, HEIGHT), 1)

        # Horizontal lines
        for i in range(-grid_spacing, HEIGHT + grid_spacing, grid_spacing):
            line_y = i - offset_y
            pygame.draw.line(screen, (50, 50, 60), (0, line_y), (WIDTH, line_y), 1)

        # Draw polished drone
        draw_polished_drone(screen, x, y, yaw, frame_count)
        
        # Draw HUD
        draw_hud(screen, roll, pitch, yaw, vx, vy)

        pygame.display.flip()
        clock.tick(60)
        frame_count += 1

except KeyboardInterrupt:
    print("Exiting...")

# Cleanup
del(pitft)
pygame.quit()
sys.exit(0)