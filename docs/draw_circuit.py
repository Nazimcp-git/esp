import matplotlib.pyplot as plt
import matplotlib.patches as patches
import shutil
import os

def create_circuit_diagram():
    fig, ax = plt.subplots(figsize=(20, 12), dpi=180)
    ax.set_facecolor('#0B0F19')
    fig.patch.set_facecolor('#0B0F19')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Title & Header
    ax.text(50, 96.5, "SIGN LANGUAGE GLOVE — COMPLETE CIRCUIT SCHEMATIC", 
            ha='center', va='center', color='#38BDF8', fontsize=18, fontweight='bold', fontfamily='sans-serif')
    ax.text(50, 93.8, "ESP32 DevKit V1 • 5x Flex Sensors (10k Pull-Down on ADC1) • MPU6050 IMU • (Speaker & DFPlayer Removed)", 
            ha='center', va='center', color='#94A3B8', fontsize=11, fontfamily='sans-serif')

    # Colors
    c_3v3 = '#EF4444'     # Red for 3.3V
    c_gnd = '#3B82F6'     # Blue / Black for GND (using vibrant blue-violet for dark theme)
    c_thumb = '#06B6D4'   # Cyan
    c_index = '#EC4899'   # Magenta
    c_middle = '#10B981'  # Emerald Green
    c_ring = '#6366F1'    # Indigo / Slate Blue
    c_pinky = '#F97316'   # Orange / Peach
    c_sda = '#38BDF8'     # Sky Blue
    c_scl = '#FBBF24'     # Amber / Yellow

    # ==========================================
    # 1. DRAW 5 FLEX SENSORS (Left side)
    # ==========================================
    sensor_x = [8, 14, 20, 26, 32]
    sensor_names = ["THUMB\n(F1)", "INDEX\n(F2)", "MIDDLE\n(F3)", "RING\n(F4)", "PINKY\n(F5)"]
    sensor_colors = [c_thumb, c_index, c_middle, c_ring, c_pinky]
    target_pins = ["GPIO 36 (VP)", "GPIO 33", "GPIO 32", "GPIO 35", "GPIO 34"]

    # Hand Section Box
    hand_box = patches.FancyBboxPatch((5, 38), 30, 52, boxstyle="round,pad=1", 
                                      facecolor='#111827', edgecolor='#1F2937', linewidth=2)
    ax.add_patch(hand_box)
    ax.text(20, 88.5, "5x 2.2\" FLEX SENSORS (ON GLOVE FINGERS)", 
            ha='center', va='center', color='#F8FAFC', fontsize=11, fontweight='bold')
    ax.text(20, 86.5, "Resistance: ~25kΩ Flat  -->  ~75kΩ Bent (90°)", 
            ha='center', va='center', color='#94A3B8', fontsize=9)

    for i, (sx, sname, scol) in enumerate(zip(sensor_x, sensor_names, sensor_colors)):
        # Flex sensor strip body
        rect = patches.FancyBboxPatch((sx-1.6, 52), 3.2, 31, boxstyle="round,pad=0.3",
                                      facecolor='#1E293B', edgecolor='#475569', linewidth=1.5)
        ax.add_patch(rect)
        
        # Carbon flex trace lines inside sensor
        for y_line in range(55, 81, 3):
            ax.plot([sx-1.1, sx+1.1], [y_line, y_line], color='#64748B', linewidth=1.5)

        ax.text(sx, 78, f"2.2\"\nFLEX", ha='center', va='center', color='#94A3B8', fontsize=7, fontweight='bold')
        ax.text(sx, 48, sname, ha='center', va='center', color=scol, fontsize=9, fontweight='bold')

        # Two sensor pin solder pads at bottom
        p_left = (sx - 0.9, 52)
        p_right = (sx + 0.9, 52)
        ax.plot(p_left[0], p_left[1], 'o', color='#F59E0B', markersize=5)
        ax.plot(p_right[0], p_right[1], 'o', color='#F59E0B', markersize=5)

        # Left pin connects to common 3.3V bus
        ax.plot([p_left[0], p_left[0]], [p_left[1], 44], color=c_3v3, linewidth=2)
        ax.plot(p_left[0], 44, 'o', color=c_3v3, markersize=4)

        # Right pin connects to voltage divider junction
        ax.plot([p_right[0], p_right[0]], [p_right[1], 35 - i*1.2], color=scol, linewidth=2)
        ax.plot(p_right[0], 35 - i*1.2, 'o', color=scol, markersize=4)

    # 3.3V Common Rail across sensors
    ax.plot([sensor_x[0]-0.9, sensor_x[-1]-0.9], [44, 44], color=c_3v3, linewidth=2.5)
    ax.text(sensor_x[0]-2.5, 44, "3.3V BUS", color=c_3v3, fontsize=9, fontweight='bold', va='center', ha='right')

    # ==========================================
    # 2. DRAW 5x 10k RESISTORS (VOLTAGE DIVIDERS)
    # ==========================================
    div_box = patches.FancyBboxPatch((5, 3), 30, 31, boxstyle="round,pad=1", 
                                     facecolor='#111827', edgecolor='#1F2937', linewidth=2)
    ax.add_patch(div_box)
    ax.text(20, 32.5, "5x 10kΩ PULL-DOWN RESISTORS", ha='center', va='center', color='#F8FAFC', fontsize=11, fontweight='bold')
    ax.text(20, 30.5, "Brown-Black-Orange (Drop: 1170 Flat -> 480 Bent)", ha='center', va='center', color='#94A3B8', fontsize=8.5)

    for i, (sx, scol, tpin) in enumerate(zip(sensor_x, sensor_colors, target_pins)):
        ry = 26 - i * 4.5
        # Junction dot
        jx = sx + 0.9
        jy = ry + 1.8
        
        # Line from sensor to junction
        ax.plot([jx, jx], [35 - i*1.2, jy], color=scol, linewidth=2)
        ax.plot(jx, jy, 'o', color='#F8FAFC', markersize=6) # Junction node

        # Resistor body
        res_rect = patches.FancyBboxPatch((jx - 0.9, ry - 1.2), 1.8, 2.4, boxstyle="round,pad=0.2",
                                          facecolor='#D97706', edgecolor='#78350F', linewidth=1)
        ax.add_patch(res_rect)
        # Resistor bands (Brown, Black, Orange)
        ax.plot([jx - 0.7, jx + 0.7], [ry + 0.6, ry + 0.6], color='#78350F', linewidth=1.5) # Brown
        ax.plot([jx - 0.7, jx + 0.7], [ry, ry], color='#000000', linewidth=1.5)             # Black
        ax.plot([jx - 0.7, jx + 0.7], [ry - 0.6, ry - 0.6], color='#EA580C', linewidth=1.5) # Orange

        ax.text(jx + 1.4, ry, "10kΩ", color='#FDE68A', fontsize=8, va='center')

        # Lead from junction to resistor top
        ax.plot([jx, jx], [jy, ry + 1.2], color='#94A3B8', linewidth=1.8)

        # Lead from resistor bottom to GND rail
        ax.plot([jx, jx], [ry - 1.2, 7], color='#94A3B8', linewidth=1.8)
        ax.plot(jx, 7, 'o', color=c_gnd, markersize=4)

        # Signal line from junction to ESP32 (routed across to right side)
        route_y = 20 + i * 3.8
        ax.plot([jx, 40], [jy, jy], color=scol, linewidth=2)
        ax.plot([40, 40], [jy, route_y], color=scol, linewidth=2)
        ax.plot([40, 58], [route_y, route_y], color=scol, linewidth=2)

    # GND bus across bottom of resistors
    ax.plot([sensor_x[0]+0.9, sensor_x[-1]+0.9], [7, 7], color=c_gnd, linewidth=2.5)
    ax.text(sensor_x[0]-2.5, 7, "GND BUS", color=c_gnd, fontsize=9, fontweight='bold', va='center', ha='right')

    # ==========================================
    # 3. DRAW ESP32 DEVKIT V1 (Center-Right)
    # ==========================================
    esp_x, esp_y = 58, 12
    esp_w, esp_h = 22, 60
    
    # Board PCB
    board = patches.FancyBboxPatch((esp_x, esp_y), esp_w, esp_h, boxstyle="round,pad=1",
                                   facecolor='#030712', edgecolor='#38BDF8', linewidth=2.5)
    ax.add_patch(board)
    
    # Metal RF Shield on top
    shield = patches.FancyBboxPatch((esp_x + 3.5, esp_y + 40), 15, 17, boxstyle="round,pad=0.4",
                                    facecolor='#1E293B', edgecolor='#94A3B8', linewidth=1.5)
    ax.add_patch(shield)
    ax.text(esp_x + 11, esp_y + 48.5, "ESP32-WROOM\n(Flash AI)", ha='center', va='center', 
            color='#E2E8F0', fontsize=9, fontweight='bold')

    # USB Port at bottom
    usb = patches.FancyBboxPatch((esp_x + 7.5, esp_y - 2), 7, 4, boxstyle="round,pad=0.2",
                                facecolor='#475569', edgecolor='#94A3B8', linewidth=1)
    ax.add_patch(usb)
    ax.text(esp_x + 11, esp_y - 0.5, "USB", ha='center', va='center', color='#F8FAFC', fontsize=7, fontweight='bold')

    # Status LED
    led = patches.Circle((esp_x + 17, esp_y + 36), 1.0, facecolor='#38BDF8', edgecolor='#0284C7', linewidth=1)
    ax.add_patch(led)
    ax.text(esp_x + 17, esp_y + 33.5, "LED (D2)", ha='center', va='center', color='#38BDF8', fontsize=7)

    # ESP32 Left Header Pins (Top to bottom)
    left_pins = [
        ("3V3", c_3v3, True),
        ("EN", '#64748B', False),
        ("VP (36)", c_thumb, True),
        ("VN (39)", '#64748B', False),
        ("D34", c_pinky, True),
        ("D35", c_ring, True),
        ("D32", c_middle, True),
        ("D33", c_index, True),
        ("D25", '#64748B', False),
        ("D26", '#64748B', False),
        ("D27", '#64748B', False),
        ("D14", '#64748B', False),
        ("D12", '#64748B', False),
        ("GND", c_gnd, True),
        ("VIN (5V)", '#F59E0B', True)
    ]

    pin_spacing = 3.6
    pin_start_y = esp_y + 54

    for i, (pname, pcol, is_used) in enumerate(left_pins):
        py = pin_start_y - i * pin_spacing
        ax.plot(esp_x, py, 'o', color=pcol if is_used else '#475569', markersize=6)
        ax.text(esp_x + 1.2, py, pname, color='#FFFFFF' if is_used else '#64748B', 
                fontsize=7.5, fontweight='bold' if is_used else 'normal', va='center')

    # ESP32 Right Header Pins
    right_pins = [
        ("D23", '#64748B', False),
        ("D22 (SCL)", c_scl, True),
        ("TX0", '#64748B', False),
        ("RX0", '#64748B', False),
        ("D21 (SDA)", c_sda, True),
        ("D19", '#64748B', False),
        ("D18", '#64748B', False),
        ("D5", '#64748B', False),
        ("TX2 (17)", '#475569', False),
        ("RX2 (16)", '#475569', False),
        ("D4", '#64748B', False),
        ("D2", '#38BDF8', False),
        ("D15", '#64748B', False),
        ("GND", c_gnd, True),
        ("3V3", c_3v3, False)
    ]

    for i, (pname, pcol, is_used) in enumerate(right_pins):
        py = pin_start_y - i * pin_spacing
        ax.plot(esp_x + esp_w, py, 'o', color=pcol if is_used else '#475569', markersize=6)
        ax.text(esp_x + esp_w - 1.2, py, pname, color='#FFFFFF' if is_used else '#64748B', 
                fontsize=7.5, fontweight='bold' if is_used else 'normal', va='center', ha='right')

    # ==========================================
    # 4. DRAW MPU6050 6-DOF IMU (Top-Right)
    # ==========================================
    mpu_x, mpu_y = 85, 52
    mpu_w, mpu_h = 12, 28

    mpu_box = patches.FancyBboxPatch((mpu_x, mpu_y), mpu_w, mpu_h, boxstyle="round,pad=0.8",
                                    facecolor='#1E3A8A', edgecolor='#3B82F6', linewidth=2)
    ax.add_patch(mpu_box)
    ax.text(mpu_x + 6, mpu_y + 24, "MPU6050\n6-DOF IMU", ha='center', va='center', 
            color='#FFFFFF', fontsize=10, fontweight='bold')
    ax.text(mpu_x + 6, mpu_y + 19, "Addr: 0x68\n(Pitch/Roll)", ha='center', va='center', 
            color='#93C5FD', fontsize=8)

    mpu_pins = [
        ("VCC", c_3v3),
        ("GND", c_gnd),
        ("SCL", c_scl),
        ("SDA", c_sda),
        ("XDA", '#64748B'),
        ("XCL", '#64748B'),
        ("AD0", c_gnd),
        ("INT", '#64748B')
    ]

    mpu_spacing = 2.0
    mpu_start_y = mpu_y + 15

    for i, (mpname, mpcol) in enumerate(mpu_pins):
        mpy = mpu_start_y - i * mpu_spacing
        ax.plot(mpu_x, mpy, 'o', color=mpcol, markersize=5)
        ax.text(mpu_x + 1.2, mpy, mpname, color='#F8FAFC', fontsize=7.5, va='center', fontweight='bold')

    # Connect MPU6050 I2C to ESP32:
    # SCL (GPIO 22)
    scl_esp_y = pin_start_y - 1 * pin_spacing
    ax.plot([mpu_x, 83, 83, esp_x + esp_w], [mpu_start_y - 2*mpu_spacing, mpu_start_y - 2*mpu_spacing, scl_esp_y, scl_esp_y], 
            color=c_scl, linewidth=2)

    # SDA (GPIO 21)
    sda_esp_y = pin_start_y - 4 * pin_spacing
    ax.plot([mpu_x, 82, 82, esp_x + esp_w], [mpu_start_y - 3*mpu_spacing, mpu_start_y - 3*mpu_spacing, sda_esp_y, sda_esp_y], 
            color=c_sda, linewidth=2)

    # MPU VCC to 3.3V bus
    ax.plot([mpu_x, 84, 84], [mpu_start_y, mpu_start_y, 82], color=c_3v3, linewidth=2)
    ax.plot([84, 52], [82, 82], color=c_3v3, linewidth=2)
    ax.plot([52, 52, esp_x], [82, pin_start_y, pin_start_y], color=c_3v3, linewidth=2)

    # MPU GND to GND bus
    ax.plot([mpu_x, 81, 81, esp_x + esp_w], [mpu_start_y - 1*mpu_spacing, mpu_start_y - 1*mpu_spacing, pin_start_y - 13*pin_spacing, pin_start_y - 13*pin_spacing], 
            color=c_gnd, linewidth=2)

    # MPU AD0 tied to GND (sets address to 0x68)
    ax.plot([mpu_x, mpu_x - 1.5, mpu_x - 1.5, mpu_x], 
            [mpu_start_y - 6*mpu_spacing, mpu_start_y - 6*mpu_spacing, mpu_start_y - 1*mpu_spacing, mpu_start_y - 1*mpu_spacing], 
            color=c_gnd, linewidth=1.5)

    # ==========================================
    # 5. POWER DISTRIBUTION
    # ==========================================
    # 3.3V rail from ESP32 to Hand
    ax.plot([esp_x, 46, 46, sensor_x[-1]-0.9], [pin_start_y, pin_start_y, 44, 44], color=c_3v3, linewidth=2.5)

    # GND rail from ESP32 to Hand resistors
    esp_gnd_y = pin_start_y - 13 * pin_spacing
    ax.plot([esp_x, 48, 48, sensor_x[-1]+0.9], [esp_gnd_y, esp_gnd_y, 7, 7], color=c_gnd, linewidth=2.5)

    # Connect ESP32 ADC pins to routed sensor wires
    ax.plot([58, esp_x], [20 + 0*3.8, pin_start_y - 2*pin_spacing], color=c_thumb, linewidth=2)  # Thumb -> VP (36)
    ax.plot([58, esp_x], [20 + 1*3.8, pin_start_y - 7*pin_spacing], color=c_index, linewidth=2)  # Index -> 33
    ax.plot([58, esp_x], [20 + 2*3.8, pin_start_y - 6*pin_spacing], color=c_middle, linewidth=2) # Middle -> 32
    ax.plot([58, esp_x], [20 + 3*3.8, pin_start_y - 5*pin_spacing], color=c_ring, linewidth=2)   # Ring -> 35
    ax.plot([58, esp_x], [20 + 4*3.8, pin_start_y - 4*pin_spacing], color=c_pinky, linewidth=2)  # Pinky -> 34

    # ==========================================
    # 6. CALLOUT NOTES & REMOVED HARDWARE BADGE
    # ==========================================
    callout_box = patches.FancyBboxPatch((84, 12), 14, 34, boxstyle="round,pad=0.8",
                                         facecolor='#18181B', edgecolor='#EF4444', linewidth=1.8, linestyle='--')
    ax.add_patch(callout_box)
    ax.text(91, 42, "REMOVED FROM\nPROJECT", ha='center', va='center', color='#EF4444', fontsize=9.5, fontweight='bold')
    ax.text(91, 33, "✖ DFPlayer Mini\n✖ 8Ω Wrist Speaker\n✖ 1kΩ TX Resistor\n✖ Bulk Capacitors\n\nGPIO 16 & 17 are\nnow FREE & UNUSED.", 
            ha='center', va='center', color='#A1A1AA', fontsize=8, linespacing=1.4)
    ax.text(91, 16.5, "Voice is generated\nvia Web Speech TTS\non Phone/PC!", ha='center', va='center', color='#34D399', fontsize=7.8, fontweight='bold')

    # Legend / Status bar
    leg_box = patches.FancyBboxPatch((5, 90.5), 93, 2.2, boxstyle="round,pad=0.2",
                                    facecolor='#1E293B', edgecolor='#334155', linewidth=1)
    ax.add_patch(leg_box)
    legend_text = "WIRE COLOR KEY:   RED = 3.3V VCC   |   BLUE = GND   |   CYAN = Thumb (36)   |   MAGENTA = Index (33)   |   GREEN = Middle (32)   |   INDIGO = Ring (35)   |   ORANGE = Pinky (34)   |   YELLOW = SCL (22)   |   SKY = SDA (21)"
    ax.text(51.5, 91.6, legend_text, ha='center', va='center', color='#E2E8F0', fontsize=7.5, fontfamily='monospace', fontweight='bold')

    plt.tight_layout()
    
    # Save outputs
    png_path = r'docs\circuit_diagram.png'
    svg_path = r'docs\circuit_diagram.svg'
    plt.savefig(png_path, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.savefig(svg_path, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.close()
    print("Circuit diagrams successfully generated!")

    # Copy to brain artifact directory for display
    artifact_dir = r'C:\Users\More\.gemini\antigravity\brain\eded3881-e3be-4018-8dc8-81f5ca4430e9'
    shutil.copy(png_path, os.path.join(artifact_dir, 'circuit_diagram.png'))
    print("Copied to artifacts directory!")

if __name__ == '__main__':
    create_circuit_diagram()
