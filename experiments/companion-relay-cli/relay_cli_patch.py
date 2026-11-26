from pathlib import Path
import sys

root = Path(sys.argv[1]).expanduser().resolve()
folder = root / "examples/companion_radio"

hp = folder / "MyMesh.h"
cp = folder / "MyMesh.cpp"

h = hp.read_text()
c = cp.read_text()

def replace_once(s, old, new):
    if s.count(old) != 1:
        raise RuntimeError("Unexpected source pattern: " + old)
    return s.replace(old, new, 1)

if "CUSTOM_RELAY_CLI_V1" in c:
    raise RuntimeError("CLI patch already applied")

# Add relay state if using an unmodified companion.
if "_ad_hoc_relay_enabled" not in h:
    anchor = "  void setBLEPin(uint32_t active_pin);"

    h = replace_once(h, anchor, anchor + """

  bool isAdHocRelayEnabled() const {
    return _ad_hoc_relay_enabled;
  }

  void setAdHocRelayEnabled(bool enabled) {
    _ad_hoc_relay_enabled = enabled;
  }
""")

    h = replace_once(
        h,
        "private:",
        "private:\n  bool _ad_hoc_relay_enabled = false;\n"
    )

    c = replace_once(
        c,
        "  return _prefs.isRepeatEn();",
        "  return _ad_hoc_relay_enabled || _prefs.isRepeatEn();"
    )

if "isAdHocRelayEnabled()" not in h:
    raise RuntimeError("Missing relay accessor")

# Reject custom relay commands received over LoRa,
# irrespective of the supplied sender timestamp.
remote_anchor = """    if (!handleCommand(text, sender_timestamp, reply)) {"""

remote_guard = """
    const char* local_only = text;
    while (*local_only == ' ') local_only++;

    if (strlen(local_only) > 4 && local_only[2] == '|') {
      local_only += 3;
    }

    if (strncmp(local_only, "get relay", 9) == 0 ||
        strncmp(local_only, "set relay", 9) == 0) {
      strcpy(reply, "Error: local CLI only");
      return;
    }

"""

c = replace_once(
    c,
    remote_anchor,
    remote_guard + remote_anchor
)

anchor = "  if (_prefs.getRadioPrefs()->handleCommand("

cli = """
  // CUSTOM_RELAY_CLI_V1
  if (strcmp(command, "get relay") == 0 ||
      strcmp(command, "set relay on") == 0 ||
      strcmp(command, "set relay off") == 0 ||
      strncmp(command, "set relay ", 10) == 0) {

    if (sender_timestamp != 0) {
      strcpy(reply, "Error: local CLI only");
      return true;
    }

    if (strcmp(command, "set relay on") == 0) {
      setAdHocRelayEnabled(true);
    } else if (strcmp(command, "set relay off") == 0) {
      setAdHocRelayEnabled(false);
    } else if (strcmp(command, "get relay") != 0) {
      strcpy(reply, "Usage: set relay on/off");
      return true;
    }

    sprintf(reply, "> ad hoc relay %s; off-grid repeat %s",
            isAdHocRelayEnabled() ? "ON" : "OFF",
            _prefs.isRepeatEn() ? "ON" : "OFF");

    return true;
  }

"""

c = replace_once(c, anchor, cli + anchor)

hp.write_text(h)
cp.write_text(c)

print("SUCCESS: Local relay CLI installed")
print("Source:", root)
