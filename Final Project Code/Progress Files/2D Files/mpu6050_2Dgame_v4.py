# Malik F (mhf68) & Hetao Y (hy668)
# Drone Minigame initial version v4
# Same visuals from previous, added GPIO reset, new obstacle generation/collision.
# November 21, 2025

import pygame
import pigame
import math
import time
import os
import sys
import random
import RPi.GPIO as GPIO

# Initial config
WIDTH, HEIGHT = 800, 480
RESET_BTN_PIN = 5  # GPIO 5

# setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(RESET_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Display setup
os.putenv('SDL_VIDEODRIVER', 'fbcon')
os.putenv('SDL_FBDEV', '/dev/fb0') 
os.putenv('SDL_MOUSEDRV', 'dummy')
os.putenv('SDL_MOUSEDEV', '/dev/null')
os.putenv('DISPLAY', '')

pygame.init()
pygame.mouse.set_visible(False)
pitft = pigame.PiTft()

# Import MPU calibration
import mpu6050_calibrate_v4 as mpu  
mpu.mpu_setup_once() 

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Drone Minigame V5")
clock = pygame.time.Clock()

# Fonts
font = pygame.font.SysFont("consolas", 22)
big_font = pygame.font.SysFont("consolas", 60, bold=True)

# Drone state (initial)
x, y = WIDTH // 2, HEIGHT // 2
vx, vy = 0, 0

ACCEL_FACTOR = 0.08    # How fast it speeds up
FRICTION = 0.95        # How fast it slows down
MAX_SPEED = 8.0        
DEADZONE = 3.0         
SPEED_SCALAR = 0.4     # Speed multiplier

# More initial variables for obstacles
obstacles = [] 
OBSTACLE_SPEED = 2.0   # Can slow or speed up
SPAWN_TIMER = 0
SPAWN_RATE = 60        # Frames between spawns

game_state = "PLAYING"
start_time = time.time()
final_time = 0.0

# Function to reset game
def reset_game():
    global x, y, vx, vy, obstacles, game_state, start_time
    x, y = WIDTH // 2, HEIGHT // 2
    vx, vy = 0, 0
    obstacles = []
    game_state = "PLAYING"
    start_time = time.time()
    print("Game Reset!")

# Function to draw better drone
def draw_polished_drone(surface, cx, cy, angle, frame_count):

    rad = math.radians(angle)
    
    # Helper to rotate points around the center (cx, cy)
    def rot(px, py):
        rx = px * math.cos(rad) - py * math.sin(rad)
        ry = px * math.sin(rad) + py * math.cos(rad)
        return (cx + rx, cy + ry)

    # Main arms in cross shape
    pygame.draw.line(surface, (50, 50, 50), rot(-45, -45), rot(45, 45), 8)
    pygame.draw.line(surface, (50, 50, 50), rot(-45, 45), rot(45, -45), 8)

    # Manipulate circles to have propeller animated.
    prop_offset = (frame_count % 3) * 2
    motors = [(-45, -45), (45, -45), (45, 45), (-45, 45)] # FL, FR, BR, BL
    
    for i, (mx, my) in enumerate(motors):
        m_screen = rot(mx, my)
        # Main housing of motor
        pygame.draw.circle(surface, (30, 30, 30), (int(m_screen[0]), int(m_screen[1])), 8)
        
        # Blade Blur
        pygame.draw.circle(surface, (255, 255, 255), (int(m_screen[0]), int(m_screen[1])), 18 + prop_offset, 2)
        pygame.draw.circle(surface, (200, 200, 200), (int(m_screen[0]), int(m_screen[1])), 10, 1)
        
        # Front is Red, back is green
        if i < 2: led_color = (255, 50, 50) # Red
        else:     led_color = (50, 255, 50) # Green
        pygame.draw.circle(surface, led_color, (int(m_screen[0]), int(m_screen[1])), 4)

    # Main body
    body_points = [rot(0, -25), rot(15, 10), rot(0, 20), rot(-15, 10)]
    pygame.draw.polygon(surface, (20, 20, 20), body_points)       
    pygame.draw.polygon(surface, (80, 100, 140), body_points, 0)  

# Make hitbox for drone
def get_drone_rect(cx, cy):
    # Slightly smaller than actual drawing
    return pygame.Rect(cx-20, cy-20, 40, 40)

# Function to draw HUD
def draw_hud_telemetry(surface, roll, pitch):
    # Same from previous versions
    s = pygame.Surface((180, 60))
    s.set_alpha(150)
    s.fill((0, 0, 0))
    surface.blit(s, (5, 5))

    r_col = (50, 255, 50) if abs(roll) > DEADZONE else (255, 255, 255)
    p_col = (50, 255, 50) if abs(pitch) > DEADZONE else (255, 255, 255)

    text1 = font.render(f"Roll : {roll:6.1f}", True, r_col)
    text2 = font.render(f"Pitch: {pitch:6.1f}", True, p_col)
    surface.blit(text1, (10, 10))
    surface.blit(text2, (10, 35))

# Main loop
frame_count = 0

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
        
        # Check GPIO Reset
        if GPIO.input(RESET_BTN_PIN) == GPIO.LOW:
            reset_game()
            time.sleep(0.2)

        if game_state == "PLAYING":
            # Read sensors
            roll, pitch, yaw = mpu.get_mpu_orientation()
            yaw = -yaw 

            # Copied physics from previous file
            eff_pitch = pitch if abs(pitch) > DEADZONE else 0
            eff_roll  = roll  if abs(roll)  > DEADZONE else 0

            thrust_forward = (eff_pitch * ACCEL_FACTOR) * SPEED_SCALAR
            thrust_strafe  = (eff_roll  * ACCEL_FACTOR) * SPEED_SCALAR

            rad_yaw = math.radians(yaw)
            acc_x = thrust_forward * math.sin(rad_yaw) + thrust_strafe * math.cos(rad_yaw)
            acc_y = thrust_forward * -math.cos(rad_yaw) + thrust_strafe * math.sin(rad_yaw)

            vx += acc_x
            vy += acc_y
            vx *= FRICTION
            vy *= FRICTION
            x += vx
            y += vy

            # Screen Bounds (Bounce)
            if x < 0: x = 0; vx = -vx * 0.5
            if x > WIDTH: x = WIDTH; vx = -vx * 0.5
            if y < 0: y = 0; vy = -vy * 0.5
            if y > HEIGHT: y = HEIGHT; vy = -vy * 0.5

            # New obstacle logic
            SPAWN_TIMER += 1
            if SPAWN_TIMER > SPAWN_RATE:
                SPAWN_TIMER = 0
                obs_w = random.randint(60, 150)
                obs_x = random.randint(0, WIDTH - obs_w)
                # Spawn above screen
                obstacles.append(pygame.Rect(obs_x, -60, obs_w, 60))

            # Move Obstacles
            for obs in obstacles:
                obs.y += OBSTACLE_SPEED
            
            # Remove off-screen
            obstacles = [o for o in obstacles if o.y < HEIGHT + 50]

            # Collision detection
            drone_rect = get_drone_rect(x, y)
            for obs in obstacles:
                if drone_rect.colliderect(obs):
                    game_state = "GAMEOVER"
                    final_time = time.time() - start_time

        # Background drawing
        screen.fill((30, 30, 35))
        
        # Grid for background, static
        grid_spacing = 50
        for i in range(0, WIDTH, grid_spacing):
            pygame.draw.line(screen, (45, 45, 55), (i, 0), (i, HEIGHT), 1)
        for i in range(0, HEIGHT, grid_spacing):
            pygame.draw.line(screen, (45, 45, 55), (0, i), (WIDTH, i), 1)

        # Draw Obstacles
        for obs in obstacles:
            pygame.draw.rect(screen, (200, 100, 50), obs)
            pygame.draw.rect(screen, (255, 150, 50), obs, 3)

        # Draw Drone
        # We need yaw for rotation, if game end use prevous yaw
        current_yaw = -mpu.get_mpu_orientation()[2] if game_state == "PLAYING" else 0
        draw_polished_drone(screen, x, y, current_yaw, frame_count)

        # Draw HUDs
        if game_state == "PLAYING":
            # Telemetry
            draw_hud_telemetry(screen, roll, pitch)
            
            # Game Timer
            curr_time = time.time() - start_time
            t_surf = font.render(f"TIME: {curr_time:.1f}s", True, (255, 255, 255))
            screen.blit(t_surf, (WIDTH - 150, 20))
            
        elif game_state == "GAMEOVER":
            # If lose
            s = pygame.Surface((WIDTH, HEIGHT))
            s.set_alpha(200)
            s.fill((0, 0, 0))
            screen.blit(s, (0, 0))
            
            # Game Over Text
            go_txt = big_font.render("GAME OVER", True, (255, 50, 50))
            score_txt = font.render(f"SURVIVED: {final_time:.2f}s", True, (255, 255, 255))
            reset_txt = font.render("Press GPIO 5 to Reset", True, (200, 200, 200))
            
            screen.blit(go_txt, go_txt.get_rect(center=(WIDTH//2, HEIGHT//2 - 40)))
            screen.blit(score_txt, score_txt.get_rect(center=(WIDTH//2, HEIGHT//2 + 20)))
            screen.blit(reset_txt, reset_txt.get_rect(center=(WIDTH//2, HEIGHT//2 + 60)))

        pygame.display.flip()
        clock.tick(60)
        frame_count += 1

# Cleanup and exit
except KeyboardInterrupt:
    print("Exiting...")
    GPIO.cleanup()
    pygame.quit()
    sys.exit()