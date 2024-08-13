# Daliserver for MegaD RPi4-RTC_PoE

1. Check install python3, python3-pigpio, pigpiod
2. Enable service pigpiod: systemctl enable pigpiod
3. Start service: systemctl start pigpiod
4. Check status: systemctl status pigpiod
5. Copy rpi4daliserver.py to /opt/rpi4daliserver/rpi4daliserver.py
6. Copy rpi4daliserver.service to /lib/systemd/system/
7. sudo chmod 644 /lib/systemd/system/rpi4daliserver.service
8. sudo systemctl daemon-reload
9. sudo systemctl enable rpi4daliserver.service
10. sudo systemctl start rpi4daliserver.service
11. sudo systemctl status rpi4daliserver.service

# TRIDONIC DALI SCI2 Emulator
1. Works with https://www.lunatone.com/en/product/dali-cockpit/ (stable)
2. https://www.tridonic.com/en/int/services/software/masterconfigurator (unstable)
3. Virtual COM software: https://www.pusr.com/ndirectory/[-Virtual-COM-Software]USR-VCOM_V3.7.2.529_Setup_1687230152.exe
