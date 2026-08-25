# EXAMPLE (CPython): peek at a Victron VE.Direct stream — raw labels/values.
#
# This is the MINIMAL exploration version. It does NOT validate the frame
# checksum, so serial noise can show you garbage values. The real logger
# (power_monitor.py, one folder up) validates every frame — that's the one
# to run unattended. Use this one to answer "is the cable even talking?"

import serial   # pip install pyserial

PORT = "/dev/ttyUSB0"    # Windows: "COM4". Find yours with:
                         #   python power_monitor.py --list-ports

with serial.Serial(PORT, 19200, timeout=3) as ser:
    while True:
        line = ser.readline().decode("ascii", errors="ignore").strip()
        if "\t" in line:
            label, value = line.split("\t", 1)
            # V = battery millivolts, PPV = panel watts, I = battery mA,
            # CS = charge state code (3=bulk 4=absorption 5=float)
            print(f"{label:10} {value}")
