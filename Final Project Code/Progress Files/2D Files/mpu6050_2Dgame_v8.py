# Malik F (mhf68) & Hetao Y (hy668)
# Added piTFT cockpit (copied over) and added palm pilot title v8
# Removed single display stuff
# November 30, 2025

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
TFT_W, TFT_H = 320, 240
TFT_DEVICE = '/dev/fb1'

# Button Setup
START_BTN_PIN = 5    # GPIO 5 for Start (Title)
RESTART_BTN_PIN = 6  # GPIO 6 for Restart (Game Over)

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(START_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(RESTART_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Display setup for Main Screen (HDMI/fb0)
os.putenv('SDL_VIDEODRIVER', 'fbcon')
os.putenv('SDL_FBDEV', '/dev/fb0') 
os.putenv('SDL_MOUSEDRV', 'dummy')
os.putenv('SDL_MOUSEDEV', '/dev/null')
os.putenv('DISPLAY', '')

pygame.init()
pygame.mouse.set_visible(False)
pitft = pigame.PiTft()

# Setup PiTFT Output (fb1) manually
tft_file = None
try:
    tft_file = open(TFT_DEVICE, 'wb')
except IOError:
    print(f"Could not open {TFT_DEVICE}. TFT output disabled.")

# Import calibration script
import mpu6050_calibrate_v4 as mpu  
mpu.mpu_setup_once() 

# Surfaces
screen = pygame.display.set_mode((WIDTH, HEIGHT))
screen_tft = pygame.Surface((TFT_W, TFT_H))
clock = pygame.time.Clock()

# Monitor fonts
font = pygame.font.SysFont("consolas", 22)
big_font = pygame.font.SysFont("consolas", 60, bold=True)
title_font = pygame.font.SysFont("consolas", 80, bold=True)

# piTFT fonts
arrow_font = pygame.font.SysFont("consolas", 20, bold=True)
cockpit_status_font = pygame.font.SysFont("consolas", 28, bold=True)

# Physics initial variables
x, y = WIDTH // 2, HEIGHT // 2
vx, vy = 0, 0

ACCEL_FACTOR = 0.08    
FRICTION = 0.95        
MAX_SPEED = 6.0        
DEADZONE = 3.0         
SPEED_SCALAR = 0.3     

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

# Cockpit generate function for piTFT
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
    
    txt_surf = cockpit_status_font.render(f"{status_text}", True, (255, 255, 255))
    txt_rect = txt_surf.get_rect(center=(cx, TFT_H - 30))
    surface.blit(txt_surf, txt_rect)
    
    surface.blit(arrow_font.render(f"P: {d_pitch:.0f}", True, (150, 150, 150)), (10, 10))
    surface.blit(arrow_font.render(f"R: {d_roll:.0f}", True, (150, 150, 150)), (10, 35))
    surface.blit(arrow_font.render(f"Y: {d_yaw:.0f}°", True, (50, 200, 255)), (TFT_W - 90, 10))


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
    
    # Init bouncing balls
    for _ in range(2):
        balls.append({
            'x': random.randint(50, WIDTH-50),
            'y': random.randint(50, HEIGHT-50),
            'vx': random.choice([-3, -2, 2, 3]),
            'vy': random.choice([-2, -1, 1, 2]),
            'color': (191, 0, 255), 
            'radius': 14 
        })

    game_state = "PLAYING"
    start_time = time.time()
    print("Game Started/Reset!")

def get_drone_points(cx, cy, angle):
    rad = math.radians(angle)
    def rot(px, py):
        rx = px * math.cos(rad) - py * math.sin(rad)
        ry = px * math.sin(rad) + py * math.cos(rad)
        return (cx + rx, cy + ry)

    points = {
        'center': (cx, cy),
        'fl': rot(-30, -30), 'fr': rot(30, -30),
        'br': rot(30, 30),   'bl': rot(-30, 30) 
    }
    return points

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
        led_color = (255, 50, 50) if i < 2 else (50, 255, 50) 
        pygame.draw.circle(surface, led_color, (int(mx), int(my)), 3)

    cx, cy = p['center']
    pygame.draw.circle(surface, (80, 100, 140), (int(cx), int(cy)), 8)

def check_drone_collision(drone_points, obstacle_list, ball_list):
    check_points = list(drone_points.values())
    for obs in obstacle_list:
        obs_rect = obs['rect']
        for px, py in check_points:
            if obs_rect.collidepoint(px, py): return True
    
    cx, cy = drone_points['center']
    drone_hit_rad = 25 
    for b in ball_list:
        dist = math.sqrt((b['x'] - cx)**2 + (b['y'] - cy)**2)
        if dist < (b['radius'] + drone_hit_rad): return True
    return False

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
                GPIO.cleanup(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                GPIO.cleanup(); sys.exit()
        
        # Return to title screen if both buttons pressed
        if GPIO.input(START_BTN_PIN) == GPIO.HIGH and GPIO.input(RESTART_BTN_PIN) == GPIO.HIGH:
            game_state = "TITLE"
            time.sleep(0.5) 

        # Title screen state
        if game_state == "TITLE":
            screen.fill((20, 20, 30))
            
            title_txt = title_font.render("Palm Pilot: 2D Mini-game", True, (80, 160, 255))
            screen.blit(title_txt, title_txt.get_rect(center=(WIDTH//2, HEIGHT//2 - 50)))

            if (frame_count // 30) % 2 == 0:
                start_txt = font.render(" Press the Blue button to start ", True, (50, 255, 50))
                start_rect = start_txt.get_rect(center=(WIDTH//2, HEIGHT//2 + 80))
                pygame.draw.rect(screen, (255, 255, 255), start_rect.inflate(20, 20), 2)
                screen.blit(start_txt, start_rect)
            
            fake_points = get_drone_points(WIDTH//2, HEIGHT//2 - 140, frame_count)
            draw_polished_drone(screen, fake_points, frame_count)
            
            # Clear TFT on Title
            if tft_file and frame_count % 30 == 0:
                screen_tft.fill((0,0,0))
                t_wait = cockpit_status_font.render("WAITING", True, (50, 50, 50))
                screen_tft.blit(t_wait, t_wait.get_rect(center=(TFT_W//2, TFT_H//2)))
                tft_file.seek(0)
                tft_file.write(screen_tft.convert(16, 0).get_buffer())

            if GPIO.input(START_BTN_PIN) == GPIO.HIGH and GPIO.input(RESTART_BTN_PIN) == GPIO.LOW:
                reset_game()
                time.sleep(0.2)

        # Playing state
        elif game_state == "PLAYING":
            roll, pitch, yaw = mpu.get_mpu_orientation()
            yaw = -yaw 

            # Update cockpit on TFT
            render_cockpit_game(screen_tft, roll, pitch, yaw)
            if tft_file:
                tft_file.seek(0)
                tft_file.write(screen_tft.convert(16, 0).get_buffer())

            # 2D Physics Logic
            eff_pitch = pitch if abs(pitch) > DEADZONE else 0
            eff_roll  = roll  if abs(roll)  > DEADZONE else 0

            thrust_forward = (eff_pitch * ACCEL_FACTOR) * SPEED_SCALAR
            thrust_strafe  = (eff_roll  * ACCEL_FACTOR) * SPEED_SCALAR

            rad_yaw = math.radians(yaw)
            acc_x = thrust_forward * math.sin(rad_yaw) + thrust_strafe * math.cos(rad_yaw)
            acc_y = thrust_forward * -math.cos(rad_yaw) + thrust_strafe * math.sin(rad_yaw)

            vx += acc_x; vy += acc_y
            vx *= FRICTION; vy *= FRICTION
            x += vx; y += vy

            if x < 0: x = 0; vx = -vx * 0.5
            if x > WIDTH: x = WIDTH; vx = -vx * 0.5
            if y < 0: y = 0; vy = -vy * 0.5
            if y > HEIGHT: y = HEIGHT; vy = -vy * 0.5

            SPAWN_TIMER += 1
            if SPAWN_TIMER > SPAWN_RATE:
                SPAWN_TIMER = 0
                obs_w = random.randint(40, 150)
                obs_x = random.randint(0, WIDTH - obs_w)
                obs_color = (50, 255, 50) if obs_w < 70 else (50, 100, 255) if obs_w < 110 else (255, 50, 50) 
                obstacles.append({'rect': pygame.Rect(obs_x, -60, obs_w, 60), 'color': obs_color})

            for obs in obstacles: obs['rect'].y += OBSTACLE_SPEED
            obstacles = [o for o in obstacles if o['rect'].y < HEIGHT + 50]

            # Ball Logic
            for b in balls:
                b['x'] += b['vx']; b['y'] += b['vy']
                if b['x'] - b['radius'] < 0: b['x'] = b['radius']; b['vx'] *= -1
                if b['x'] + b['radius'] > WIDTH: b['x'] = WIDTH - b['radius']; b['vx'] *= -1
                if b['y'] - b['radius'] < 0: b['y'] = b['radius']; b['vy'] *= -1
                if b['y'] + b['radius'] > HEIGHT: b['y'] = HEIGHT - b['radius']; b['vy'] *= -1

                for obs in obstacles:
                    r = obs['rect']
                    closest_x = max(r.left, min(b['x'], r.right))
                    closest_y = max(r.top, min(b['y'], r.bottom))
                    dist_x = b['x'] - closest_x
                    dist_y = b['y'] - closest_y
                    distance = math.sqrt(dist_x**2 + dist_y**2)
                    
                    if distance < b['radius']:
                        overlap = b['radius'] - distance
                        if distance == 0: distance = 0.1
                        nx = dist_x / distance; ny = dist_y / distance
                        b['x'] += nx * overlap; b['y'] += ny * overlap
                        if abs(nx) > abs(ny): b['vx'] *= -1
                        else: b['vy'] *= -1

            current_points = get_drone_points(x, y, yaw)
            if check_drone_collision(current_points, obstacles, balls):
                game_state = "GAMEOVER"
                final_time = time.time() - start_time

            # Drawing Main Screen
            screen.fill((30, 30, 35))
            for i in range(0, WIDTH, 50): pygame.draw.line(screen, (45, 45, 55), (i, 0), (i, HEIGHT), 1)
            for i in range(0, HEIGHT, 50): pygame.draw.line(screen, (45, 45, 55), (0, i), (WIDTH, i), 1)

            for obs in obstacles:
                pygame.draw.rect(screen, obs['color'], obs['rect'])
                pygame.draw.rect(screen, (255, 255, 255), obs['rect'], 2)

            for b in balls:
                pygame.draw.circle(screen, b['color'], (int(b['x']), int(b['y'])), b['radius'])
                pygame.draw.circle(screen, (255, 255, 255), (int(b['x']), int(b['y'])), b['radius'], 1)

            draw_polished_drone(screen, current_points, frame_count)
            draw_hud_telemetry(screen, roll, pitch)
            screen.blit(font.render(f"TIME: {time.time() - start_time:.1f}s", True, (255, 255, 255)), (WIDTH - 150, 20))

        # Game over state
        elif game_state == "GAMEOVER":
            s = pygame.Surface((WIDTH, HEIGHT)); s.set_alpha(200); s.fill((0, 0, 0))
            screen.blit(s, (0, 0))
            
            screen.blit(big_font.render("GAME OVER", True, (255, 50, 50)), (WIDTH//2 - 140, HEIGHT//2 - 40))
            screen.blit(font.render(f"SURVIVED: {final_time:.2f}s", True, (255, 255, 255)), (WIDTH//2 - 80, HEIGHT//2 + 20))
            screen.blit(font.render("           Press the Yellow Button to restart ", True, (200, 200, 200)), (WIDTH//2 - 180, HEIGHT//2 + 60))

            if GPIO.input(RESTART_BTN_PIN) == GPIO.HIGH and GPIO.input(START_BTN_PIN) == GPIO.LOW:
                reset_game()
                time.sleep(0.2)

        pygame.display.flip()
        clock.tick(60)
        frame_count += 1

except KeyboardInterrupt:
    print("Exiting...")
    if tft_file: tft_file.close()
    GPIO.cleanup()
    pygame.quit()
    sys.exit()