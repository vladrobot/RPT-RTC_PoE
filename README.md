# Daliserver for MegaD RPi4-RTC_PoE

1. Check install python3, python3-pigpio, pigpiod
2. Enable service pigpiod: systemctl enable pigpiod
   Start service: systemctl start pigpiod
   Check status: systemctl status pigpiod
3. Copy rpi4daliserver.py to /opt/rpi4daliserver/rpi4daliserver.py
4. Copy rpi4daliserver.service to /lib/systemd/system/
   sudo chmod 644 /lib/systemd/system/rpi4daliserver.service
   sudo systemctl daemon-reload
   sudo systemctl enable rpi4daliserver.service
   sudo systemctl start rpi4daliserver.service
   sudo systemctl status rpi4daliserver.service

# TRIDONIC DALI SCI2 Emulator
Works with https://www.lunatone.com/en/product/dali-cockpit/ (stable)
https://www.tridonic.com/en/int/services/software/masterconfigurator (unstable)
Virtual COM software: https://www.pusr.com/ndirectory/[-Virtual-COM-Software]USR-VCOM_V3.7.2.529_Setup_1687230152.exe
