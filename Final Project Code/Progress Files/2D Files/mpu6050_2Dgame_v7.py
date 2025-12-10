# Malik F (mhf68) & Hetao Y (hy668)
# Better ball physics (bounces off everything) and back to title button using gpio 5 and 6. v7
# November 27, 2025

import pygame
import pigame
import math
import time
import os
import sys
import random
import RPi.GPIO as GPIO

# Display Initialize
WIDTH, HEIGHT = 800, 480
START_BTN_PIN = 5    # GPIO 5 for Start (Title)
RESTART_BTN_PIN = 6  # GPIO 6 for Restart (Game Over)

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(START_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(RESTART_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Display setup for Main Screen (fb0)
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
pygame.display.set_caption("Palm Pilot: 2D Mini-game")
clock = pygame.time.Clock()

# Monitor fonts
font = pygame.font.SysFont("consolas", 22)
big_font = pygame.font.SysFont("consolas", 60, bold=True)
title_font = pygame.font.SysFont("consolas", 80, bold=True)

# Physics initial variables
x, y = WIDTH // 2, HEIGHT // 2
vx, vy = 0, 0

ACCEL_FACTOR = 0.08    
FRICTION = 0.95        
MAX_SPEED = 8.0        
DEADZONE = 3.0         
SPEED_SCALAR = 0.4     

# Obstacle and ball variables
obstacles = [] 
balls = []
OBSTACLE_SPEED = 2.0   
SPAWN_TIMER = 0
SPAWN_RATE = 60        

# Game state variables
game_state = "TITLE" 
start_time = time.time()
final_time = 0.0

# Reset game state and variables
def reset_game():
    global x, y, vx, vy, obstacles, balls, game_state, start_time
    
    # Recalibrate/Setup sensor again on reset
    print("Recalibrating sensor...")
    mpu.mpu_setup_once()
    
    x, y = WIDTH // 2, HEIGHT // 2
    vx, vy = 0, 0
    obstacles = []
    balls = []
    
    # Init bouncing balls (Made slightly bigger)
    for _ in range(2):
        balls.append({
            'x': random.randint(50, WIDTH-50),
            'y': random.randint(50, HEIGHT-50),
            'vx': random.choice([-4, -3, 3, 4]),
            'vy': random.choice([-4, -3, 3, 4]),
            'color': (255, 200, 50), 
            'radius': 12 # Bigger balls
        })

    game_state = "PLAYING"
    start_time = time.time()
    print("Game Started/Reset!")

# Calculate drone corner points based on rotation
def get_drone_points(cx, cy, angle):
    rad = math.radians(angle)
    def rot(px, py):
        rx = px * math.cos(rad) - py * math.sin(rad)
        ry = px * math.sin(rad) + py * math.cos(rad)
        return (cx + rx, cy + ry)

    points = {
        'center': (cx, cy),
        'fl': rot(-30, -30),
        'fr': rot(30, -30),
        'br': rot(30, 30), 
        'bl': rot(-30, 30) 
    }
    return points

# Draw drone body, arms, and motors
def draw_polished_drone(surface, points, frame_count):
    p = points
    pygame.draw.line(surface, (50, 50, 50), p['fl'], p['br'], 6)
    pygame.draw.line(surface, (50, 50, 50), p['fr'], p['bl'], 6)

    prop_offset = (frame_count % 3) * 2
    motor_keys = ['fl', 'fr', 'br', 'bl']
    
    for i, key in enumerate(motor_keys):
        mx, my = p[key]
        pygame.draw.circle(surface, (30, 30, 30), (int(mx), int(my)), 6)
        pygame.draw.circle(surface, (255, 255, 255), (int(mx), int(my)), 12 + prop_offset, 1)
        if i < 2: led_color = (255, 50, 50) 
        else:     led_color = (50, 255, 50) 
        pygame.draw.circle(surface, led_color, (int(mx), int(my)), 3)

    cx, cy = p['center']
    pygame.draw.circle(surface, (80, 100, 140), (int(cx), int(cy)), 8)

# Check if drone hits any obstacles or balls
def check_drone_collision(drone_points, obstacle_list, ball_list):
    check_points = list(drone_points.values())
    for obs in obstacle_list:
        obs_rect = obs['rect']
        for px, py in check_points:
            if obs_rect.collidepoint(px, py):
                return True
    
    cx, cy = drone_points['center']
    drone_hit_rad = 25 
    for b in ball_list:
        dist = math.sqrt((b['x'] - cx)**2 + (b['y'] - cy)**2)
        if dist < (b['radius'] + drone_hit_rad):
            return True
    return False

# Draw background for telemetry data
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
        
        # Return to title screen if both buttons pressed
        if GPIO.input(START_BTN_PIN) == GPIO.HIGH and GPIO.input(RESTART_BTN_PIN) == GPIO.HIGH:
            game_state = "TITLE"
            time.sleep(0.5) # Debounce for holding both

        # Title screen state
        if game_state == "TITLE":
            screen.fill((20, 20, 30))
            
            title_txt = title_font.render("DRONE V7", True, (80, 160, 255))
            sub_txt = font.render("Minigame", True, (200, 200, 200))
            
            t_rect = title_txt.get_rect(center=(WIDTH//2, HEIGHT//2 - 50))
            screen.blit(title_txt, t_rect)
            screen.blit(sub_txt, (WIDTH//2 - 40, HEIGHT//2 + 10))

            # Blink effect for start text
            if (frame_count // 30) % 2 == 0:
                start_txt = font.render(" Press the Blue button to start ", True, (50, 255, 50))
                start_rect = start_txt.get_rect(center=(WIDTH//2, HEIGHT//2 + 80))
                
                # Draw box around start text
                padding = 10
                box_rect = start_rect.inflate(padding * 2, padding * 2)
                pygame.draw.rect(screen, (255, 255, 255), box_rect, 2)
                
                screen.blit(start_txt, start_rect)
            
            fake_points = get_drone_points(WIDTH//2, HEIGHT//2 - 140, frame_count)
            draw_polished_drone(screen, fake_points, frame_count)

            # Only check Start button if NOT holding both (handled above)
            if GPIO.input(START_BTN_PIN) == GPIO.HIGH and GPIO.input(RESTART_BTN_PIN) == GPIO.LOW:
                reset_game()
                time.sleep(0.2)

        # Playing state
        elif game_state == "PLAYING":
            roll, pitch, yaw = mpu.get_mpu_orientation()
            yaw = -yaw 

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

            if x < 0: x = 0; vx = -vx * 0.5
            if x > WIDTH: x = WIDTH; vx = -vx * 0.5
            if y < 0: y = 0; vy = -vy * 0.5
            if y > HEIGHT: y = HEIGHT; vy = -vy * 0.5

            SPAWN_TIMER += 1
            if SPAWN_TIMER > SPAWN_RATE:
                SPAWN_TIMER = 0
                obs_w = random.randint(40, 150)
                obs_x = random.randint(0, WIDTH - obs_w)
                
                if obs_w < 70:   obs_color = (50, 255, 50) 
                elif obs_w < 110: obs_color = (50, 100, 255) 
                else:             obs_color = (255, 50, 50) 

                new_obs = {
                    'rect': pygame.Rect(obs_x, -60, obs_w, 60),
                    'color': obs_color
                }
                obstacles.append(new_obs)

            for obs in obstacles:
                obs['rect'].y += OBSTACLE_SPEED
            
            obstacles = [o for o in obstacles if o['rect'].y < HEIGHT + 50]

            # Ball Logic with Improved Collision
            for b in balls:
                b['x'] += b['vx']
                b['y'] += b['vy']

                # Screen Boundary Bounce
                if b['x'] - b['radius'] < 0: 
                    b['x'] = b['radius']
                    b['vx'] *= -1
                if b['x'] + b['radius'] > WIDTH: 
                    b['x'] = WIDTH - b['radius']
                    b['vx'] *= -1
                if b['y'] - b['radius'] < 0: 
                    b['y'] = b['radius']
                    b['vy'] *= -1
                if b['y'] + b['radius'] > HEIGHT: 
                    b['y'] = HEIGHT - b['radius']
                    b['vy'] *= -1

                # Obstacle Collision (Elastic + Push out)
                for obs in obstacles:
                    r = obs['rect']
                    
                    # Find closest point on rect to circle center
                    closest_x = max(r.left, min(b['x'], r.right))
                    closest_y = max(r.top, min(b['y'], r.bottom))
                    
                    dist_x = b['x'] - closest_x
                    dist_y = b['y'] - closest_y
                    distance = math.sqrt(dist_x**2 + dist_y**2)
                    
                    if distance < b['radius']:
                        # Collision detected
                        
                        # Resolve Overlap (Push ball out of rect)
                        overlap = b['radius'] - distance
                        if distance == 0: distance = 0.1 # Safety
                        
                        # Normal vector from rect to ball
                        nx = dist_x / distance
                        ny = dist_y / distance
                        
                        b['x'] += nx * overlap
                        b['y'] += ny * overlap
                        
                        # Bounce Logic
                        # If normal is more horizontal, flip X. Else flip Y.
                        if abs(nx) > abs(ny):
                            b['vx'] *= -1
                        else:
                            b['vy'] *= -1

            current_points = get_drone_points(x, y, yaw)
            if check_drone_collision(current_points, obstacles, balls):
                game_state = "GAMEOVER"
                final_time = time.time() - start_time

            screen.fill((30, 30, 35))
            
            grid_spacing = 50
            for i in range(0, WIDTH, grid_spacing):
                pygame.draw.line(screen, (45, 45, 55), (i, 0), (i, HEIGHT), 1)
            for i in range(0, HEIGHT, grid_spacing):
                pygame.draw.line(screen, (45, 45, 55), (0, i), (WIDTH, i), 1)

            for obs in obstacles:
                pygame.draw.rect(screen, obs['color'], obs['rect'])
                pygame.draw.rect(screen, (255, 255, 255), obs['rect'], 2)

            for b in balls:
                pygame.draw.circle(screen, b['color'], (int(b['x']), int(b['y'])), b['radius'])
                pygame.draw.circle(screen, (255, 255, 255), (int(b['x']), int(b['y'])), b['radius'], 1)

            draw_points = get_drone_points(x, y, -mpu.get_mpu_orientation()[2])
            draw_polished_drone(screen, draw_points, frame_count)

            draw_hud_telemetry(screen, roll, pitch)
            curr_time = time.time() - start_time
            t_surf = font.render(f"TIME: {curr_time:.1f}s", True, (255, 255, 255))
            screen.blit(t_surf, (WIDTH - 150, 20))

        # Game over state
        elif game_state == "GAMEOVER":
            s = pygame.Surface((WIDTH, HEIGHT))
            s.set_alpha(200)
            s.fill((0, 0, 0))
            screen.blit(s, (0, 0))
            
            go_txt = big_font.render("GAME OVER", True, (255, 50, 50))
            score_txt = font.render(f"SURVIVED: {final_time:.2f}s", True, (255, 255, 255))
            reset_txt = font.render("Press the Yellow Button to restart", True, (200, 200, 200))
            
            screen.blit(go_txt, go_txt.get_rect(center=(WIDTH//2, HEIGHT//2 - 40)))
            screen.blit(score_txt, score_txt.get_rect(center=(WIDTH//2, HEIGHT//2 + 20)))
            screen.blit(reset_txt, reset_txt.get_rect(center=(WIDTH//2, HEIGHT//2 + 60)))

            if GPIO.input(RESTART_BTN_PIN) == GPIO.HIGH and GPIO.input(START_BTN_PIN) == GPIO.LOW:
                reset_game()
                time.sleep(0.2)

        pygame.display.flip()
        clock.tick(60)
        frame_count += 1

# Exit and cleanup
except KeyboardInterrupt:
    print("Exiting...")
    GPIO.cleanup()
    pygame.quit()
    sys.exit()