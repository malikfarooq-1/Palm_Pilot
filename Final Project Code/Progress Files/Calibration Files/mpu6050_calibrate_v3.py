# Malik F (mhf68) & Hetao Y (hy668)
# Script for initial interfacing of MPU chip v3 
# Added EMA LPF (a=0.3) and z-axis gravity fix
# Removed list based moving average, heavy output smoothing, and auto drift correction.
# November 14, 2025 

import smbus2
import time
import math
import numpy as np
import json
import matplotlib.pyplot as plt
from collections import deque

# MPU6050 Registers and Addresses
MPU6050_ADDR = 0x68
PWR_MGMT_1 = 0x6B
ACCEL_XOUT_H = 0x3B
GYRO_XOUT_H = 0x43

bus = smbus2.SMBus(1)

# Low-pass filter variables
Ax_prev, Ay_prev, Az_prev = 0, 0, 0
Gx_prev, Gy_prev, Gz_prev = 0, 0, 0

# Initialize our MPU
def init_mpu6050():
    # Wake up MPU 
    try:
        bus.write_byte_data(MPU6050_ADDR, PWR_MGMT_1, 0)
        time.sleep(0.1)
        print("MPU6050 Initialized.")
    except Exception as e:
        print(f"Error initializing MPU: {e}")

# Read raw data 
def read_raw_data(addr):
    #16-bit data to readable form 
    try:
        high = bus.read_byte_data(MPU6050_ADDR, addr)
        low = bus.read_byte_data(MPU6050_ADDR, addr + 1)
        value = ((high << 8) | low)
        if value > 32768:
            value -= 65536
        return value
    except OSError:
        return 0

# Read accelerometer and gyroscope data
def get_accel_gyro_data():
    # Get all data from here
    ax = read_raw_data(ACCEL_XOUT_H)
    ay = read_raw_data(ACCEL_XOUT_H + 2)
    az = read_raw_data(ACCEL_XOUT_H + 4)
    gx = read_raw_data(GYRO_XOUT_H)
    gy = read_raw_data(GYRO_XOUT_H + 2)
    gz = read_raw_data(GYRO_XOUT_H + 4)

    # Scale conversion
    Ax = ax / 16384.0
    Ay = ay / 16384.0
    Az = az / 16384.0
    Gx = gx / 131.0
    Gy = gy / 131.0
    Gz = gz / 131.0

    return Ax, Ay, Az, Gx, Gy, Gz

# Calibration Setup
def calibrate_mpu(samples=200):
    # Average readings over sample range
    print("Calibrating MPU6050... Keep the sensor FLAT and STILL.")
    acc_bias = np.zeros(3)
    gyro_bias = np.zeros(3)

    for i in range(samples):
        Ax, Ay, Az, Gx, Gy, Gz = get_accel_gyro_data()
        acc_bias += np.array([Ax, Ay, Az])
        gyro_bias += np.array([Gx, Gy, Gz])
        time.sleep(0.01)

    # Find average bias
    acc_bias /= samples
    gyro_bias /= samples

    # Z axis fix
    acc_bias[2] -= 1.0 

    # Print bias for accelerometer and gryoscope
    print("Calibration complete.")
    print(f"Accel bias (offset from 1g): {acc_bias}")
    print(f"Gyro bias:  {gyro_bias}")

    return acc_bias, gyro_bias

# Calibration save initially
def save_calibration(acc_bias, gyro_bias, filename="mpu_calib.json"):
    # Save for future use
    with open(filename, 'w') as f:
        json.dump({'acc_bias': acc_bias.tolist(), 'gyro_bias': gyro_bias.tolist()}, f)
    print(f"Calibration saved to {filename}")

# Loading saved calibration
def load_calibration(filename="mpu_calib.json"):
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        print(f"Loaded calibration from {filename}")
        return np.array(data['acc_bias']), np.array(data['gyro_bias'])
    except FileNotFoundError:
        print("Calibration file not found — performing new calibration.")
        result = calibrate_mpu()
        save_calibration(result[0], result[1])
        return result

# Orientation Calculation
def compute_orientation(acc, gyro, dt, angles):
    # Compute roll, pitch, yaw
    Ax, Ay, Az = acc
    Gx, Gy, Gz = gyro

    # Integrate gyro data
    roll_gyro = angles[0] + Gx * dt
    pitch_gyro = angles[1] + Gy * dt
    yaw_gyro = angles[2] + Gz * dt

    # Calculate accel-based roll/pitch
    dist = math.sqrt(Ay*Ay + Az*Az)
    roll_acc  = math.degrees(math.atan2(Ay, dist))
    
    dist_p = math.sqrt(Ax*Ax + Az*Az)
    pitch_acc = math.degrees(math.atan2(-Ax, dist_p))

    # Complementary filter
    alpha = 0.98

    roll  = alpha * roll_gyro  + (1 - alpha) * roll_acc
    pitch = alpha * pitch_gyro + (1 - alpha) * pitch_acc
    
    yaw = yaw_gyro  # Gyro-only yaw

    return [roll, pitch, yaw]

# Get initial pitch, yaw, roll for pygame
def mpu_setup_once():
    # Single call before main game loop
    global acc_bias_pg, gyro_bias_pg, angles_pg, prev_time_pg
    global Ax_prev, Ay_prev, Az_prev

    init_mpu6050()
    acc_bias_pg, gyro_bias_pg = load_calibration()

    # Initialize first
    Ax_start, Ay_start, Az_start, _, _, _ = get_accel_gyro_data()
    Ax_prev, Ay_prev, Az_prev = Ax_start, Ay_start, Az_start

    angles_pg = [0, 0, 0]
    prev_time_pg = time.perf_counter()

    print("MPU ready for Pygame control.")


def get_mpu_orientation():
    # Return with a LPF
    global acc_bias_pg, gyro_bias_pg, angles_pg, prev_time_pg
    global Ax_prev, Ay_prev, Az_prev
    global Gx_prev, Gy_prev, Gz_prev

    Ax, Ay, Az, Gx, Gy, Gz = get_accel_gyro_data()

    # Remove bias
    Ax -= acc_bias_pg[0]
    Ay -= acc_bias_pg[1]
    Az -= acc_bias_pg[2]
    Gx -= gyro_bias_pg[0]
    Gy -= gyro_bias_pg[1]
    Gz -= gyro_bias[2]

    # Fast Low Pass Filter for Accel
    lpf_alpha = 0.3
    Ax = lpf_alpha * Ax + (1 - lpf_alpha) * Ax_prev
    Ay = lpf_alpha * Ay + (1 - lpf_alpha) * Ay_prev
    Az = lpf_alpha * Az + (1 - lpf_alpha) * Az_prev
    
    Ax_prev, Ay_prev, Az_prev = Ax, Ay, Az

    # Gyro LPF
    Gx = 0.7 * Gx + 0.3 * Gx_prev
    Gy = 0.7 * Gy + 0.3 * Gy_prev
    Gz = 0.7 * Gz + 0.3 * Gz_prev
    
    Gx_prev, Gy_prev, Gz_prev = Gx, Gy, Gz

    # dt
    current_time = time.perf_counter()
    dt = current_time - prev_time_pg
    prev_time_pg = current_time

    # Calculate final angles
    angles_pg = compute_orientation([Ax, Ay, Az],
                                   [Gx, Gy, Gz],
                                   dt, angles_pg)

    return angles_pg[0], angles_pg[1], angles_pg[2]

# Reading live time (Analysis)
def live_reading():
    init_mpu6050()
    acc_bias, gyro_bias = load_calibration()

    angles = [0, 0, 0]
    prev_time = time.perf_counter()
    
    # Initialize LPF seeds
    Ax_prev, Ay_prev, Az_prev = 0, 0, 0

    print("\n Reading data... Press Ctrl+C to stop.\n")
    try:
        while True:
            Ax, Ay, Az, Gx, Gy, Gz = get_accel_gyro_data()

            # Remove biases
            Ax -= acc_bias[0]
            Ay -= acc_bias[1]
            Az -= acc_bias[2]
            Gx -= gyro_bias[0]
            Gy -= gyro_bias[1]
            Gz -= gyro_bias[2]

            # Fast LPF
            lpf_alpha = 0.3
            Ax = lpf_alpha * Ax + (1 - lpf_alpha) * Ax_prev
            Ay = lpf_alpha * Ay + (1 - lpf_alpha) * Ay_prev
            Az = lpf_alpha * Az + (1 - lpf_alpha) * Az_prev
            Ax_prev, Ay_prev, Az_prev = Ax, Ay, Az

            current_time = time.perf_counter()
            dt = current_time - prev_time
            prev_time = current_time

            angles = compute_orientation([Ax, Ay, Az], [Gx, Gy, Gz], dt, angles)
            print(f"Roll: {angles[0]:6.2f}°, Pitch: {angles[1]:6.2f}°, Yaw: {angles[2]:6.2f}°")

            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nTerminated by user.")

# Plot data from readings
def live_plot(duration=30, window_size=200):
    # initialize mpu
    init_mpu6050()
    acc_bias, gyro_bias = load_calibration()

    # Setup plot
    plt.ion()
    fig, ax = plt.subplots()
    ax.set_title("MPU6050 Real-Time Orientation")
    ax.set_xlabel("Samples")
    ax.set_ylabel("Angle (°)")
    ax.set_ylim([-180, 180])

    x_data = deque(maxlen=window_size)
    roll_data = deque(maxlen=window_size)
    pitch_data = deque(maxlen=window_size)
    yaw_data = deque(maxlen=window_size)

    roll_line, = ax.plot([], [], label="Roll", color="r")
    pitch_line, = ax.plot([], [], label="Pitch", color="g")
    yaw_line, = ax.plot([], [], label="Yaw", color="b")
    ax.legend(loc="upper right")

    plt.show(block=False)

    angles = [0, 0, 0]
    prev_time = time.perf_counter()
    start_time = time.perf_counter()
    
    # Initialize LPF seeds locally
    Ax_prev, Ay_prev, Az_prev = 0, 0, 0
    Gx_prev, Gy_prev, Gz_prev = 0, 0, 0

    print("Live plot running... Close the window or press Ctrl+C to stop.")

    try:
        while True:
            Ax, Ay, Az, Gx, Gy, Gz = get_accel_gyro_data()
            Ax -= acc_bias[0]
            Ay -= acc_bias[1]
            Az -= acc_bias[2]
            Gx -= gyro_bias[0]
            Gy -= gyro_bias[1]
            Gz -= gyro_bias[2]

            # Fast Accel LPF
            lpf_alpha = 0.3
            Ax = lpf_alpha * Ax + (1 - lpf_alpha) * Ax_prev
            Ay = lpf_alpha * Ay + (1 - lpf_alpha) * Ay_prev
            Az = lpf_alpha * Az + (1 - lpf_alpha) * Az_prev
            Ax_prev, Ay_prev, Az_prev = Ax, Ay, Az
            
            # Gyro LPF
            Gx = 0.7 * Gx + 0.3 * Gx_prev
            Gy = 0.7 * Gy + 0.3 * Gy_prev
            Gz = 0.7 * Gz + 0.3 * Gz_prev
            Gx_prev, Gy_prev, Gz_prev = Gx, Gy, Gz

            current_time = time.perf_counter()
            dt = current_time - prev_time
            prev_time = current_time

            angles = compute_orientation([Ax, Ay, Az], [Gx, Gy, Gz], dt, angles)

            x_data.append(len(x_data))
            roll_data.append(angles[0])
            pitch_data.append(angles[1])
            yaw_data.append(angles[2])

            roll_line.set_data(x_data, roll_data)
            pitch_line.set_data(x_data, pitch_data)
            yaw_line.set_data(x_data, yaw_data)
            ax.set_xlim(max(0, len(x_data) - window_size), len(x_data))
            # Increase interval slightly to prevent plot lag
            fig.canvas.draw()
            fig.canvas.flush_events()

            if duration and (time.perf_counter() - start_time > duration):
                break

            # Sleep slightly less than live_reading to keep plot smooth
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n Plot terminated by user.")
    finally:
        plt.ioff()
        plt.show()

# Start Loop
if __name__ == "__main__":
    live_reading()
    # live_plot(duration=None)