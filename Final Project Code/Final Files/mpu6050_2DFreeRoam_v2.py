# Malik F (mhf68) & Hetao Y (hy668)
# Drone 2D Free Roam V2
# Added game_wrap function. This means commenting out initializations, and letting our main file call these functions.
# December 5, 2025

import pygame
import pigame
import math
import time
import os
import sys
import RPi.GPIO as GPIO
import mpu6050_calibrate_v4 as mpu 

# Display Initialize
WIDTH, HEIGHT = 800, 480
TFT_W, TFT_H = 320, 240
TFT_DEVICE = '/dev/fb1'

# Button Setup
START_BTN_PIN = 5    # GPIO 5 for Start (Title)
RESTART_BTN_PIN = 6  # GPIO 6 for Reset Position

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

# Setup piTFT manually (fb1)
# tft_file = None
# try:
#     tft_file = open(TFT_DEVICE, 'wb')
# except IOError:
#     print(f"Could not open {TFT_DEVICE}. TFT output disabled.")
 
# mpu.mpu_setup_once() 

# Screen surfaces
# screen = pygame.display.set_mode((WIDTH, HEIGHT))
# screen_tft = pygame.Surface((TFT_W, TFT_H))
# clock = pygame.time.Clock()

# Monitor fonts
# font = pygame.font.SysFont("consolas", 22)
# title_font = pygame.font.SysFont("consolas", 80, bold=True)
font = None
title_font = None

# piTFT fonts
# arrow_font = pygame.font.SysFont("consolas", 20, bold=True)
# cockpit_status_font = pygame.font.SysFont("consolas", 28, bold=True)
arrow_font = None
cockpit_status_font = None

# Physics initial variables
x, y = WIDTH // 2, HEIGHT // 2
vx, vy = 0, 0

ACCEL_FACTOR = 0.08    
FRICTION = 0.95        
MAX_SPEED = 6.0        
DEADZONE = 3.0         
SPEED_SCALAR = 0.3     

# Game state variables
game_state = "TITLE" 

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
        # draw center circle when not moving
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
    if cockpit_status_font:
        txt_surf = cockpit_status_font.render(f"{status_text}", True, (255, 255, 255))
        txt_rect = txt_surf.get_rect(center=(cx, TFT_H - 30))
        surface.blit(txt_surf, txt_rect)
    
    # Show raw values on display
    if arrow_font:
        surface.blit(arrow_font.render(f"P: {d_pitch:.0f}", True, (150, 150, 150)), (10, 10))
        surface.blit(arrow_font.render(f"R: {d_roll:.0f}", True, (150, 150, 150)), (10, 35))
        surface.blit(arrow_font.render(f"Y: {d_yaw:.0f}°", True, (50, 200, 255)), (TFT_W - 90, 10))


# Reset drone position variables
def reset_drone_position():
    global x, y, vx, vy, game_state
    
    # Recalibrate sensor again on reset
    print("Recalibrating sensor...")
    mpu.mpu_setup_once()
    
    x, y = WIDTH // 2, HEIGHT // 2
    vx, vy = 0, 0

    game_state = "PLAYING"
    print("Free Roam Reset!")

# Calculate drone corner points based on rotation.
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

# Draw drone body, arms, and motors
def draw_polished_drone(surface, points, frame_count):
    p = points
    pygame.draw.line(surface, (50, 50, 50), p['fl'], p['br'], 6)
    pygame.draw.line(surface, (50, 50, 50), p['fr'], p['bl'], 6)

    # Animation effect for propellers.
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

# Draw background for telemetry data
def draw_hud_telemetry(surface, roll, pitch):
    s = pygame.Surface((180, 60))
    s.set_alpha(150)
    s.fill((0, 0, 0))
    surface.blit(s, (5, 5))

    r_col = (50, 255, 50) if abs(roll) > DEADZONE else (255, 255, 255)
    p_col = (50, 255, 50) if abs(pitch) > DEADZONE else (255, 255, 255)

    if font:
        text1 = font.render(f"Roll : {roll:6.1f}", True, r_col)
        text2 = font.render(f"Pitch: {pitch:6.1f}", True, p_col)
        surface.blit(text1, (10, 10))
        surface.blit(text2, (10, 35))

# WRAPPER FUNCTION
def run_game(main_screen, main_pitft):
    global x, y, vx, vy, game_state
    global font, title_font, arrow_font, cockpit_status_font
    global frame_count, menu_hold_timer # Define these locally/globally

    # Use passed in surfaces
    screen = main_screen
    pitft = main_pitft

    # Init Local Resources
    font = pygame.font.SysFont("consolas", 22)
    title_font = pygame.font.SysFont("consolas", 80, bold=True)
    arrow_font = pygame.font.SysFont("consolas", 20, bold=True)
    cockpit_status_font = pygame.font.SysFont("consolas", 28, bold=True)

    tft_file = None
    try:
        tft_file = open(TFT_DEVICE, 'wb')
    except IOError:
        print(f"Could not open {TFT_DEVICE}. TFT output disabled.")

    screen_tft = pygame.Surface((TFT_W, TFT_H))
    clock = pygame.time.Clock()
    
    mpu.mpu_setup_once() 

    # Reset vars
    x, y = WIDTH // 2, HEIGHT // 2
    vx, vy = 0, 0
    game_state = "TITLE"
    frame_count = 0
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
                time.sleep(0.5) 

            # Hold blue button to return to launcher
            if GPIO.input(START_BTN_PIN) == GPIO.HIGH:
                if menu_hold_timer == 0:
                    menu_hold_timer = time.time()
                elif time.time() - menu_hold_timer > 2.0:
                    print("Returning to Launcher...")
                    if tft_file: tft_file.close() 
                    running = False
            else:
                menu_hold_timer = 0

            # Title screen state
            if game_state == "TITLE":
                screen.fill((20, 20, 30))
                
                title_txt = title_font.render("Free Roam Mode", True, (80, 160, 255))
                screen.blit(title_txt, title_txt.get_rect(center=(WIDTH//2, HEIGHT//2 - 50)))

                # Blink effect for start button
                if (frame_count // 30) % 2 == 0:
                    start_txt = font.render(" Press the Blue button to Fly ", True, (50, 255, 50))
                    start_rect = start_txt.get_rect(center=(WIDTH//2, HEIGHT//2 + 80))
                    pygame.draw.rect(screen, (255, 255, 255), start_rect.inflate(20, 20), 2)
                    screen.blit(start_txt, start_rect)
                
                # Draw fake drone for title screen
                fake_points = get_drone_points(WIDTH//2, HEIGHT//2 - 140, frame_count)
                draw_polished_drone(screen, fake_points, frame_count)
                
                # piTFT waiting screen if on title menu
                if tft_file and frame_count % 30 == 0:
                    screen_tft.fill((0,0,0))
                    t_wait = cockpit_status_font.render("WAITING", True, (50, 50, 50))
                    screen_tft.blit(t_wait, t_wait.get_rect(center=(TFT_W//2, TFT_H//2)))
                    tft_file.seek(0)
                    tft_file.write(screen_tft.convert(16, 0).get_buffer())

                # start game when blue button is pressed
                if GPIO.input(START_BTN_PIN) == GPIO.HIGH and GPIO.input(RESTART_BTN_PIN) == GPIO.LOW:
                    reset_drone_position()
                    time.sleep(0.2)

            # Playing state
            elif game_state == "PLAYING":
                roll, pitch, yaw = mpu.get_mpu_orientation()
                yaw = -yaw 

                # Update cockpit view on piTFT
                render_cockpit_game(screen_tft, roll, pitch, yaw)
                if tft_file:
                    tft_file.seek(0)
                    tft_file.write(screen_tft.convert(16, 0).get_buffer())

                # Physics and acceleration based on mpu input
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

                # Keep drone within screen bounds
                if x < 0: x = 0; vx = -vx * 0.5
                if x > WIDTH: x = WIDTH; vx = -vx * 0.5
                if y < 0: y = 0; vy = -vy * 0.5
                if y > HEIGHT: y = HEIGHT; vy = -vy * 0.5

                current_points = get_drone_points(x, y, yaw)

                # Draw background
                screen.fill((30, 30, 35))
                
                # Draw infinite grid effect *
                for i in range(0, WIDTH, 50): pygame.draw.line(screen, (45, 45, 55), (i, 0), (i, HEIGHT), 1)
                for i in range(0, HEIGHT, 50): pygame.draw.line(screen, (45, 45, 55), (0, i), (WIDTH, i), 1)

                draw_polished_drone(screen, current_points, frame_count)
                draw_hud_telemetry(screen, roll, pitch)
                
                # Instructions on screen
                help_txt = font.render("Press Yellow button to Reset Pos", True, (100, 100, 100))
                screen.blit(help_txt, (WIDTH - 300, HEIGHT - 30))

                # Reset position when yellow button is pressed
                if GPIO.input(RESTART_BTN_PIN) == GPIO.HIGH and GPIO.input(START_BTN_PIN) == GPIO.LOW:
                    reset_drone_position()
                    time.sleep(0.2)

            pygame.display.flip()
            clock.tick(60)
            frame_count += 1

    # exit and cleanup
    except KeyboardInterrupt:
        pass
    finally:
        print("Cleaning up local game resources...")
        if tft_file: tft_file.close()
        # GPIO.cleanup()
        # pygame.quit()
        # sys.exit()
        return