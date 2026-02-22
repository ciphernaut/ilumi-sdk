# Diagnostic Access Enablement

To safely grant the agent the ability to autonomously test physical changes (via webcam) and capture raw Bluetooth protocol logs, please configure your system to grant limited access without requiring an interactive password prompt.

There are two primary ways to allow this: **Group Modification** (recommended for video) and **Sudoers Configuration** (needed for btmon).

## 1. Video Access (`/dev/video0`)

The safest and most common way to allow webcam access is to add the user running the agent to the `video` group. This requires no `sudo` during runtime.

### Group Method (Recommended)
Run the following command once, then **log out and log back in** for it to take effect:
```bash
sudo usermod -aG video $USER
```

### Sudoers Method (Alternative)
If you prefer not to use groups and instead want to explicitely allow the agent to run `chmod` on the video device or run `ffmpeg` as root:

Create a file named `/etc/sudoers.d/agent-video` using `sudo visudo /etc/sudoers.d/agent-video`:
```text
# Allow agent to change permissions on the primary video device
ALL ALL=(ALL) NOPASSWD: /usr/bin/chmod 666 /dev/video0
```

---

## 2. Bluetooth HCI Snoop Log (`btmon`)

`btmon` requires root privileges to attach to the Bluetooth HCI interface and sniff traffic.

Create a file named `/etc/sudoers.d/agent-btmon` using `sudo visudo /etc/sudoers.d/agent-btmon`:
```text
# Allow agent to run btmon without a password for protocol debugging
ALL ALL=(ALL) NOPASSWD: /usr/bin/btmon
```

## Summary of Agent Actions

Once these permissions are in place, the agent can perform the following autonomous workflow:

1. **Start `btmon` background capture:** `sudo btmon -w /tmp/capture.snoop > /dev/null 2>&1 &`
2. **Execute Python scripts:** e.g., `python3 enroll.py` or `python3 on.py`
3. **Capture visual result:** `ffmpeg -f video4linux2 -i /dev/video0 -vframes 1 snapshot.jpg -y`
4. **Analyze visual result:** The agent views the `snapshot.jpg` using multi-modal tools to confirm if the bulb is successfully outputting the commanded light.
5. **Analyze network trace:** If the visual check fails, the agent kills `btmon` and reads the captured raw packet bytes to determine why the bulb rejected the payload.

---

## 3. Capturing the Official App Trace (Android HCI Snoop)

To bypass the need to reverse-engineer the packet payloads, you can capture the absolute source of truth directly from your Android phone: the exact Bluetooth conversation between the official Ilumi app and the bulb during enrollment.

1. **Enable Developer Options:**
   - Go to **Settings > About Phone**.
   - Tap **Build Number** 7 times.
2. **Enable Bluetooth Tracing:**
   - Go to **Settings > System > Developer Options**.
   - Toggle **Enable Bluetooth HCI snoop log** to ON.
   - If prompted with options like "Filtered" or "Full", select **Full**.
3. **Restart Bluetooth:**
   - Turn your phone's Bluetooth OFF and then ON again to activate logging.
4. **Perform the Action:**
   - Open the official Ilumi app.
   - Run through the pairing/enrollment process for the bulb exactly once.
   - Close the app.
6. **Retrieve the Log:**
   - Option A (Easiest): Go to Developer Options and select **Take bug report** (Full). When finished, it will output a `.zip` file. Extract this and check the `FS/data/misc/bluetooth/logs/` or `FS/data/log/bt/` folder for `btsnoop_hci.log`.
   - Option B (ADB Bugreport): Connect your phone via USB and run `adb bugreport capture`. This will generate a `capture.zip` file in your current directory. Extract this zip file, and look inside the extracted folder for `FS/data/misc/bluetooth/logs/btsnoop_hci.log` or a similar path.
6. **Provide to Agent:**
   - Place the extracted `btsnoop_hci.log` (or `.cfa` via some devices) right into this project folder.
   - Tag me and say "The android trace is ready for analysis."
