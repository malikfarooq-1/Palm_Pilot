# Malik F (mhf68) & Hetao Y (hy668)
# Added better collision detection (for 5 points) and color coded obstacles v5
# Removed simple collision detection.
# November 27, 2025

import pygame
import pigame
import math
import time
import os
import sys
import random
import RPi.GPIO as GPIO

# Display and button config
WIDTH, HEIGHT = 800, 480
RESET_BTN_PIN = 5  # GPIO 5 for Reset

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(RESET_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Display setup (can use fb1 for piTFT)
os.putenv('SDL_VIDEODRIVER', 'fbcon')
os.putenv('SDL_FBDEV', '/dev/fb0') 
os.putenv('SDL_MOUSEDRV', 'dummy')
os.putenv('SDL_MOUSEDEV', '/dev/null')
os.putenv('DISPLAY', '')

pygame.init()
pygame.mouse.set_visible(False)
pitft = pigame.PiTft()

# Import calibration script
import mpu6050_calibrate_v4 as mpu  
mpu.mpu_setup_once() 

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Drone Minigame V5")
clock = pygame.time.Clock()

# Centralized font
font = pygame.font.SysFont("consolas", 22)
big_font = pygame.font.SysFont("consolas", 60, bold=True)

# physics initial variables and multipliers
x, y = WIDTH // 2, HEIGHT // 2
vx, vy = 0, 0

ACCEL_FACTOR = 0.08    
FRICTION = 0.95        
MAX_SPEED = 8.0        
DEADZONE = 3.0         
SPEED_SCALAR = 0.4     

# Game variables for obstacles
obstacles = [] 
OBSTACLE_SPEED = 2.0   
SPAWN_TIMER = 0
SPAWN_RATE = 60        

game_state = "PLAYING"
start_time = time.time()
final_time = 0.0

# Resetting game function.
def reset_game():
    global x, y, vx, vy, obstacles, game_state, start_time
    x, y = WIDTH // 2, HEIGHT // 2
    vx, vy = 0, 0
    obstacles = []
    game_state = "PLAYING"
    start_time = time.time()
    print("Game Reset!")

# Getting points for drone for collision purposes.
def get_drone_points(cx, cy, angle):
    
    rad = math.radians(angle)
    
    def rot(px, py):
        rx = px * math.cos(rad) - py * math.sin(rad)
        ry = px * math.sin(rad) + py * math.cos(rad)
        return (cx + rx, cy + ry)

    # Arm lengths (can make bigger or smaller)
    points = {
        'center': (cx, cy),
        'fl': rot(-30, -30), # Front Left
        'fr': rot(30, -30),  # Front Right
        'br': rot(30, 30),   # Back Right
        'bl': rot(-30, 30)   # Back Left
    }
    return points

# More polished drone look
def draw_polished_drone(surface, points, frame_count):
    
    # Arms in a cross
    p = points
    pygame.draw.line(surface, (50, 50, 50), p['fl'], p['br'], 6)
    pygame.draw.line(surface, (50, 50, 50), p['fr'], p['bl'], 6)

    # Manipulate circles to make propeller movemment
    prop_offset = (frame_count % 3) * 2
    motor_keys = ['fl', 'fr', 'br', 'bl']
    
    for i, key in enumerate(motor_keys):
        mx, my = p[key]
        # Main propeller circle
        pygame.draw.circle(surface, (30, 30, 30), (int(mx), int(my)), 6)
        # Movememnt to simulate actual props moving
        pygame.draw.circle(surface, (255, 255, 255), (int(mx), int(my)), 12 + prop_offset, 1)
        # LEDs for front and back
        if i < 2: led_color = (255, 50, 50) # RED
        else:     led_color = (50, 255, 50) # GREEN
        pygame.draw.circle(surface, led_color, (int(mx), int(my)), 3)

    # Main body drawing
    cx, cy = p['center']
    pygame.draw.circle(surface, (80, 100, 140), (int(cx), int(cy)), 8)

# Drone collision function
def check_drone_collision(drone_points, obstacle_list):

    # Using points from before to make collision logic
    check_points = list(drone_points.values())
    
    for obs in obstacle_list:
        obs_rect = obs['rect']
        for px, py in check_points:
            if obs_rect.collidepoint(px, py):
                return True
    return False

# Draw HUD
def draw_hud_telemetry(surface, roll, pitch):
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

# Main Loop
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
        if GPIO.input(RESET_BTN_PIN) == GPIO.HIGH:
            reset_game()
            time.sleep(0.2)

        if game_state == "PLAYING":
            # Use sensor and translate to movement on screen
            roll, pitch, yaw = mpu.get_mpu_orientation()
            yaw = -yaw 

            # Physics of sensor input, includes multipliers and friction for realistic movement
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

            # Obstacle logic, different colors to add some polishing look
            SPAWN_TIMER += 1
            if SPAWN_TIMER > SPAWN_RATE:
                SPAWN_TIMER = 0
                obs_w = random.randint(40, 150) # Range allowed
                obs_x = random.randint(0, WIDTH - obs_w)
                
                # Determine Color based on Width (size)
                if obs_w < 70:
                    obs_color = (50, 255, 50) # GREEN (Small)
                elif obs_w < 110:
                    obs_color = (50, 100, 255) # BLUE (Med)
                else:
                    obs_color = (255, 50, 50) # RED (Large)

                # Store as Dict
                new_obs = {
                    'rect': pygame.Rect(obs_x, -60, obs_w, 60),
                    'color': obs_color
                }
                obstacles.append(new_obs)

            # Move Obstacles
            for obs in obstacles:
                obs['rect'].y += OBSTACLE_SPEED
            
            # Remove off-screen
            obstacles = [o for o in obstacles if o['rect'].y < HEIGHT + 50]

            # Collision if drone intersects
            current_points = get_drone_points(x, y, yaw)
            if check_drone_collision(current_points, obstacles):
                game_state = "GAMEOVER"
                final_time = time.time() - start_time

        # background and grid drawing
        screen.fill((30, 30, 35))
        
        grid_spacing = 50
        for i in range(0, WIDTH, grid_spacing):
            pygame.draw.line(screen, (45, 45, 55), (i, 0), (i, HEIGHT), 1)
        for i in range(0, HEIGHT, grid_spacing):
            pygame.draw.line(screen, (45, 45, 55), (0, i), (WIDTH, i), 1)

        # Draw Obstacles (using colors above)
        for obs in obstacles:
            pygame.draw.rect(screen, obs['color'], obs['rect'])
            # Border of shape
            pygame.draw.rect(screen, (255, 255, 255), obs['rect'], 2)

        # Draw Drone
        current_yaw = -mpu.get_mpu_orientation()[2] if game_state == "PLAYING" else 0
        draw_points = get_drone_points(x, y, current_yaw)
        draw_polished_drone(screen, draw_points, frame_count)

        # Draw HUDs
        if game_state == "PLAYING":
            draw_hud_telemetry(screen, roll, pitch)
            curr_time = time.time() - start_time
            t_surf = font.render(f"TIME: {curr_time:.1f}s", True, (255, 255, 255))
            screen.blit(t_surf, (WIDTH - 150, 20))
            
        elif game_state == "GAMEOVER":
            s = pygame.Surface((WIDTH, HEIGHT))
            s.set_alpha(200)
            s.fill((0, 0, 0))
            screen.blit(s, (0, 0))
            
            go_txt = big_font.render("GAME OVER", True, (255, 50, 50))
            score_txt = font.render(f"SURVIVED: {final_time:.2f}s", True, (255, 255, 255))
            reset_txt = font.render("Press GPIO 5 to Reset", True, (200, 200, 200))
            
            screen.blit(go_txt, go_txt.get_rect(center=(WIDTH//2, HEIGHT//2 - 40)))
            screen.blit(score_txt, score_txt.get_rect(center=(WIDTH//2, HEIGHT//2 + 20)))
            screen.blit(reset_txt, reset_txt.get_rect(center=(WIDTH//2, HEIGHT//2 + 60)))

        pygame.display.flip()
        clock.tick(60)
        frame_count += 1

# Exit and cleanup
except KeyboardInterrupt:
    print("Exiting...")
    GPIO.cleanup()
    pygame.quit()
    sys.exit()