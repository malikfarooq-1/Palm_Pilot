# Malik F (mhf68) & Hetao Y (hy668)
# Script for initial interfacing of MPU chip v2
# Added list based moving average for accelerometer, heavy output smoothing, and auto-drift correction
# Removed time.time which is not precise enough.
# November 10, 2025

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

# Moving average setup
acc_lpf = {
    "Ax": deque(maxlen=40),
    "Ay": deque(maxlen=40),
    "Az": deque(maxlen=40)
}

# gyro LPF previous values
Gx_prev = 0
Gy_prev = 0
Gz_prev = 0

# Initialize our MPU
def init_mpu6050():
    # Wake up MPU 
    bus.write_byte_data(MPU6050_ADDR, PWR_MGMT_1, 0)
    time.sleep(0.1)
    print("MPU6050 Initialized.")

# Read raw data 
def read_raw_data(addr):
    #16-bit data to readable form 
    high = bus.read_byte_data(MPU6050_ADDR, addr)
    low = bus.read_byte_data(MPU6050_ADDR, addr + 1)
    value = ((high << 8) | low)
    if value > 32768:
        value -= 65536
    return value

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
    print("Calibrating MPU6050... Keep the sensor still.")
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

    # Print bias for accelerometer and gryoscope
    print("Calibration complete.")
    print(f"Accel bias: {acc_bias}")
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
        return calibrate_mpu()

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
    roll_acc  = math.degrees(math.atan2(Ay, math.sqrt(Ax*Ax + Az*Az)))
    pitch_acc = math.degrees(math.atan2(-Ax, math.sqrt(Ay*Ay + Az*Az)))

    # Complementary filter
    alpha_fast = 1.0     # stable short-term
    alpha_slow = 0.995   # slow drift removal

    roll_fast  = roll_gyro
    pitch_fast = pitch_gyro

    roll  = alpha_slow * roll_fast  + (1 - alpha_slow) * roll_acc
    pitch = alpha_slow * pitch_fast + (1 - alpha_slow) * pitch_acc

    yaw = yaw_gyro  # Gyro-only yaw (no magnetometer)

    return [roll, pitch, yaw]

# Get initial pitch, yaw, roll for pygame
def mpu_setup_once():
    
    # Single call before main game loop
    global acc_bias_pg, gyro_bias_pg, angles_pg, prev_time_pg
    global roll_f_ema, pitch_f_ema, yaw_f_ema

    init_mpu6050()
    acc_bias_pg, gyro_bias_pg = load_calibration()

    angles_pg = [0, 0, 0]
    prev_time_pg = time.perf_counter()

    roll_f_ema = 0
    pitch_f_ema = 0
    yaw_f_ema = 0

    print("MPU ready for Pygame control.")


def get_mpu_orientation():
    
    # Return with a LPF and exponential smoothing applied.
    global acc_bias_pg, gyro_bias_pg, angles_pg, prev_time_pg
    global roll_f_ema, pitch_f_ema, yaw_f_ema
    global Gx_prev, Gy_prev, Gz_prev
    Ax, Ay, Az, Gx, Gy, Gz = get_accel_gyro_data()

    # Remove bias
    Ax -= acc_bias_pg[0]
    Ay -= acc_bias_pg[1]
    Az -= acc_bias_pg[2]
    Gx -= gyro_bias_pg[0]
    Gy -= gyro_bias_pg[1]
    Gz -= gyro_bias_pg[2]

    # LPF (moving average based)
    acc_lpf["Ax"].append(Ax)
    acc_lpf["Ay"].append(Ay)
    acc_lpf["Az"].append(Az)
    Ax_f = sum(acc_lpf["Ax"]) / len(acc_lpf["Ax"])
    Ay_f = sum(acc_lpf["Ay"]) / len(acc_lpf["Ay"])
    Az_f = sum(acc_lpf["Az"]) / len(acc_lpf["Az"])

    # Accel fix
    if abs(Az_f) < 0.2:
        Az_f = 0.2 if Az_f >= 0 else -0.2

    # gyro lpf
    Gx = 0.7*Gx + 0.3*Gx_prev
    Gy = 0.7*Gy + 0.3*Gy_prev
    Gz = 0.7*Gz + 0.3*Gz_prev

    Gx_prev, Gy_prev, Gz_prev = Gx, Gy, Gz

    # dt
    current_time = time.perf_counter()
    dt = current_time - prev_time_pg
    prev_time_pg = current_time

    # Raw filter output
    angles_pg = compute_orientation([Ax_f, Ay_f, Az_f],
                                   [Gx, Gy, Gz],
                                   dt, angles_pg)

    raw_roll, raw_pitch, raw_yaw = angles_pg

    # Exponential smoothing
    alpha = 0.1  # smoothing factor

    roll_f_ema = alpha * raw_roll + (1 - alpha) * roll_f_ema
    pitch_f_ema = alpha * raw_pitch + (1 - alpha) * pitch_f_ema
    yaw_f_ema = alpha * raw_yaw + (1 - alpha) * yaw_f_ema

    return roll_f_ema, pitch_f_ema, yaw_f_ema

# Reading live time (Analysis)
def live_reading():
    init_mpu6050()
    acc_bias, gyro_bias = load_calibration()

    angles = [0, 0, 0]
    prev_time = time.perf_counter()

    gyro_drift = np.array([0.0, 0.0, 0.0])
    still_count = 0

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

            # Low-pass filter accel
            acc_lpf["Ax"].append(Ax)
            acc_lpf["Ay"].append(Ay)
            acc_lpf["Az"].append(Az)
            Ax_f = sum(acc_lpf["Ax"]) / len(acc_lpf["Ax"])
            Ay_f = sum(acc_lpf["Ay"]) / len(acc_lpf["Ay"])
            Az_f = sum(acc_lpf["Az"]) / len(acc_lpf["Az"])

            current_time = time.perf_counter()
            dt = current_time - prev_time
            prev_time = current_time

            # Auto drift correction
            if abs(Ax_f) < 0.05 and abs(Ay_f) < 0.05 and abs(Az_f - 1.0) < 0.1:
                if abs(Gx) < 0.5 and abs(Gy) < 0.5 and abs(Gz) < 0.5:
                    still_count += 1
                    if still_count > 50:
                        gyro_bias += np.array([Gx, Gy, Gz]) * 0.01
                else:
                    still_count = 0

            angles = compute_orientation([Ax_f, Ay_f, Az_f], [Gx, Gy, Gz], dt, angles)
            print(f"Roll: {angles[0]:6.2f}°, Pitch: {angles[1]:6.2f}°, Yaw: {angles[2]:6.2f}°")

            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nTerminated by user.")

# Plot data from readings
def live_plot(duration=30, window_size=200):
    # intialize mpu
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

            # LPF
            acc_lpf["Ax"].append(Ax)
            acc_lpf["Ay"].append(Ay)
            acc_lpf["Az"].append(Az)
            Ax_f = sum(acc_lpf["Ax"]) / len(acc_lpf["Ax"])
            Ay_f = sum(acc_lpf["Ay"]) / len(acc_lpf["Ay"])
            Az_f = sum(acc_lpf["Az"]) / len(acc_lpf["Az"])

            current_time = time.perf_counter()
            dt = current_time - prev_time
            prev_time = current_time

            angles = compute_orientation([Ax_f, Ay_f, Az_f], [Gx, Gy, Gz], dt, angles)

            x_data.append(len(x_data))
            roll_data.append(angles[0])
            pitch_data.append(angles[1])
            yaw_data.append(angles[2])

            roll_line.set_data(x_data, roll_data)
            pitch_line.set_data(x_data, pitch_data)
            yaw_line.set_data(x_data, yaw_data)
            ax.set_xlim(max(0, len(x_data) - window_size), len(x_data))
            fig.canvas.draw()
            fig.canvas.flush_events()

            if duration and (time.perf_counter() - start_time > duration):
                break

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n Plot terminated by user.")
    finally:
        plt.ioff()
        plt.show()

# Start Loop
if __name__ == "__main__":
    live_reading()
    #live_plot(duration=None)
