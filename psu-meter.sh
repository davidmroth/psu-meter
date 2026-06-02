#!/bin/bash
# corsair_power.sh - Get PSU power level

POWER_PATH=$(ls /sys/class/hwmon/hwmon*/power1_input 2>/dev/null | head -1)
if [ -n "$POWER_PATH" ]; then
  WATTS=$(cat "$POWER_PATH")
  echo "$((WATTS / 1000000)) W"  # Convert microWatts to Watts
else
  echo "No Corsair PSU sensor found"
fi
