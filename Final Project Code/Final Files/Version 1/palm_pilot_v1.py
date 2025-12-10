# Malik F (mhf68) & Hetao Y (hy668)
# Palm Pilot Main Script V1 - Basically allows one time selection of a gamemode. Is fixed in v2.
# December 3, 2025

import pygame
import pigame
import os
import sys
import time
import subprocess
import RPi.GPIO as GPIO

# Display Initialize
WIDTH, HEIGHT = 800, 480
SELECT_BTN_PIN = 5   # GPIO 5 for Select
CYCLE_BTN_PIN = 6    # GPIO 6 for Change Mode

# Game mode configuration
MODES = [
    {"name": "2D Minigame",          "file": "mpu6050_2Dminigame_v1.py"},
    {"name": "2D Minigame (EXTREME)", "file": "mpu6050_2Dminigamehard_v1.py"},
    {"name": "2D Free Roam",         "file": "mpu6050_2DFreeRoam_v1.py"},
    {"name": "3D Free Roam (WIP)",   "file": "mpu6050_3DFreeRoam_v1.py"}
]

# Display setup for Main Screen (fb0)
os.putenv('SDL_VIDEODRIVER', 'fbcon')
os.putenv('SDL_FBDEV', '/dev/fb0') 
os.putenv('SDL_MOUSEDRV', 'dummy')
os.putenv('SDL_MOUSEDEV', '/dev/null')
os.putenv('DISPLAY', '')

pygame.init()
pygame.mouse.set_visible(False)

# Initialize piTFT 
pitft = pigame.PiTft()

# Screen surfaces
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Palm Pilot")

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(SELECT_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(CYCLE_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Monitor fonts
title_font = pygame.font.SysFont("consolas", 80, bold=True)
sub_font = pygame.font.SysFont("consolas", 30)
item_font = pygame.font.SysFont("consolas", 40)

# Draw menu interface
def draw_menu(selection_index):
    screen.fill((20, 20, 30)) # Dark background

    # Title
    t_surf = title_font.render("Palm Pilot V1", True, (80, 160, 255))
    s_surf = sub_font.render("by Malik F & Hetao Y", True, (150, 150, 150))
    
    screen.blit(t_surf, t_surf.get_rect(center=(WIDTH//2, 80)))
    screen.blit(s_surf, s_surf.get_rect(center=(WIDTH//2, 130)))

    # Menu Items
    start_y = 200
    spacing = 60
    
    for i, mode in enumerate(MODES):
        color = (255, 255, 255)
        prefix = "  "
        
        # Highlight option
        if i == selection_index:
            color = (50, 255, 50) # Green
            prefix = "> "
            
            # Draw box around selection
            rect = pygame.Rect(WIDTH//2 - 250, start_y + (i * spacing) - 10, 500, 50)
            pygame.draw.rect(screen, (50, 50, 50), rect)
            pygame.draw.rect(screen, (100, 255, 100), rect, 2)

        txt = item_font.render(prefix + mode["name"], True, color)
        screen.blit(txt, txt.get_rect(center=(WIDTH//2, start_y + (i * spacing) + 15)))

    # Instructions
    inst = sub_font.render("YEL: Change Mode | BLUE: Select", True, (100, 100, 100))
    screen.blit(inst, inst.get_rect(center=(WIDTH//2, HEIGHT - 30)))

    pygame.display.flip()

# Launch game subprocess
def launch_game(filename):
    print(f"Launching {filename}...")

    # Clean up Pygame/GPIO before handing off to subprocess
    pygame.quit()
    GPIO.cleanup()
    
    # Run the script and wait for it to finish
    try:
        subprocess.call([sys.executable, filename])
    except Exception as e:
        print(f"Failed to launch: {e}")
    
    # Exit launcher
    print("Game session ended. Exiting Palm Pilot.")
    sys.exit()

# Main Loop
current_selection = 0
running = True
btn_cycle_prev = GPIO.HIGH
btn_select_prev = GPIO.HIGH

try:
    while running:

        # Input Handling
        btn_cycle = GPIO.input(CYCLE_BTN_PIN)
        btn_select = GPIO.input(SELECT_BTN_PIN)

        # Cycle (Yellow Button)
        if btn_cycle == GPIO.HIGH and btn_cycle_prev == GPIO.LOW:
            current_selection = (current_selection + 1) % len(MODES)
        
        # Select (Blue Button)
        if btn_select == GPIO.HIGH and btn_select_prev == GPIO.LOW:
            launch_game(MODES[current_selection]["file"])
            # Script will exit inside launch_game, so no need for further logic

        btn_cycle_prev = btn_cycle
        btn_select_prev = btn_select

        # Draw
        draw_menu(current_selection)
        
        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
                
        time.sleep(0.05)

# Exit and cleanup
except KeyboardInterrupt:
    pass
finally:
    GPIO.cleanup()
    pygame.quit()