from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"patch target not found: {label}")
    return text.replace(old, new, 1)


# More host HID interfaces for composite keyboards/mice behind a hub.
tusb = Path("headers/tusb_config.h")
text = tusb.read_text()
text = replace_once(text, "#define CFG_TUH_HID 4", "#define CFG_TUH_HID 8", "CFG_TUH_HID")
tusb.write_text(text)

# Extend the keyboard/mouse listener with independent states and FPS aim shaping.
header = Path("headers/addons/keyboard_host_listener.h")
h = header.read_text()
h = replace_once(
    h,
    """    uint8_t getKeycodeFromModifier(uint8_t modifier);\n    void preprocess_report();\n    void process_kbd_report(uint8_t dev_addr, hid_keyboard_report_t const *report);\n    void process_mouse_report(uint8_t dev_addr, hid_mouse_report_t const *report);\n    uint16_t scaleMouseToJoystick(int8_t mouseVal);\n""",
    """    uint8_t getKeycodeFromModifier(uint8_t modifier);\n    void resetKeyboardState();\n    void process_kbd_report(uint8_t dev_addr, hid_keyboard_report_t const *report);\n    void process_mouse_report(uint8_t dev_addr, hid_mouse_report_t const *report);\n    void updateFpsAim();\n    float smoothMouseDelta(int32_t delta, float &previous);\n    float shapeMousePercent(float delta, bool adsActive) const;\n    uint16_t percentToJoystick(float signedPercent) const;\n""",
    "method declarations",
)
h = replace_once(
    h,
    "    GamepadState _keyboard_host_state;\n",
    "    GamepadState _keyboard_host_state;\n    GamepadState _mouse_host_state;\n",
    "mouse state",
)
h = replace_once(
    h,
    "    bool mouseActive;\n",
    """    bool mouseActive;\n    int32_t mouseAccumX;\n    int32_t mouseAccumY;\n    float smoothMouseX;\n    float smoothMouseY;\n    bool mouseRightHeld;\n    uint32_t nextAimUpdateUs;\n""",
    "FPS aim members",
)
header.write_text(h)

source = Path("src/addons/keyboard_host_listener.cpp")
s = source.read_text()
s = replace_once(
    s,
    "#include <algorithm>\n",
    "#include <algorithm>\n#include <cmath>\n#include \"pico/time.h\"\n",
    "includes",
)
s = replace_once(
    s,
    "#define GAMEPAD_JOYSTICK_MAX_I32 static_cast<int32_t>(GAMEPAD_JOYSTICK_MAX)\n",
    """#define GAMEPAD_JOYSTICK_MAX_I32 static_cast<int32_t>(GAMEPAD_JOYSTICK_MAX)\n\nnamespace {\nconstexpr float FPS_MIN_OUTPUT = 9.0f;\nconstexpr float FPS_CURVE_GAMMA = 1.6f;\nconstexpr float FPS_SMOOTHING_KEEP = 0.25f;\nconstexpr float FPS_ADS_MULTIPLIER = 0.40f;\nconstexpr uint32_t FPS_AIM_PERIOD_US = 8333; // ~120 Hz\n}\n""",
    "FPS constants",
)
s = replace_once(
    s,
    """  mouseX = 0;\n  mouseY = 0;\n  mouseZ = 0;\n  mouseActive = false;\n}\n""",
    """  mouseX = 0;\n  mouseY = 0;\n  mouseZ = 0;\n  mouseActive = false;\n  mouseAccumX = 0;\n  mouseAccumY = 0;\n  smoothMouseX = 0.0f;\n  smoothMouseY = 0.0f;\n  mouseRightHeld = false;\n  nextAimUpdateUs = time_us_32() + FPS_AIM_PERIOD_US;\n\n  _keyboard_host_state = GamepadState{};\n  _mouse_host_state = GamepadState{};\n}\n""",
    "setup state init",
)

start = s.index("void KeyboardHostListener::process() {")
end = s.index("void KeyboardHostListener::mount(", start)
s = s[:start] + """void KeyboardHostListener::process() {\n  Gamepad *gamepad = Storage::getInstance().GetGamepad();\n\n  if (_keyboard_host_mounted == true) {\n    gamepad->state.dpad    |= _keyboard_host_state.dpad;\n    gamepad->state.buttons |= _keyboard_host_state.buttons;\n    if (!gamepad->hasAnalogTriggers) {\n      gamepad->state.lt |= _keyboard_host_state.lt;\n      gamepad->state.rt |= _keyboard_host_state.rt;\n    }\n  }\n\n  if (_mouse_host_mounted == true) {\n    updateFpsAim();\n    gamepad->state.buttons |= _mouse_host_state.buttons;\n    if (!gamepad->hasAnalogTriggers) {\n      gamepad->state.lt |= _mouse_host_state.lt;\n      gamepad->state.rt |= _mouse_host_state.rt;\n    }\n\n    if (mouseMovementMode == MOUSE_MOVEMENT_LEFT_ANALOG) {\n      gamepad->state.lx = _mouse_host_state.lx;\n      gamepad->state.ly = _mouse_host_state.ly;\n    } else if (mouseMovementMode == MOUSE_MOVEMENT_RIGHT_ANALOG) {\n      gamepad->state.rx = _mouse_host_state.rx;\n      gamepad->state.ry = _mouse_host_state.ry;\n    }\n\n    gamepad->auxState.sensors.mouse.active = mouseActive;\n    if (mouseActive == true) {\n      gamepad->auxState.sensors.mouse.enabled = true;\n      gamepad->auxState.sensors.mouse.x = mouseX;\n      gamepad->auxState.sensors.mouse.y = mouseY;\n      gamepad->auxState.sensors.mouse.z = mouseZ;\n      mouseActive = false;\n    }\n  }\n}\n\n""" + s[end:]

s = replace_once(
    s,
    """void KeyboardHostListener::unmount(uint8_t dev_addr) {\n    if ( _keyboard_host_mounted == true && _keyboard_dev_addr == dev_addr ) {\n        _keyboard_host_mounted = false;\n        _keyboard_dev_addr = DEV_ADDR_NONE;\n        _keyboard_instance = 0;\n    } else if ( _mouse_host_mounted == true && _mouse_dev_addr == dev_addr ) {\n        Gamepad *gamepad = Storage::getInstance().GetGamepad();\n        gamepad->auxState.sensors.mouse.enabled = false;\n        _mouse_host_mounted = false;\n        _mouse_dev_addr = DEV_ADDR_NONE;\n        _mouse_instance = 0;\n    }\n}\n""",
    """void KeyboardHostListener::unmount(uint8_t dev_addr) {\n    if ( _keyboard_host_mounted == true && _keyboard_dev_addr == dev_addr ) {\n        _keyboard_host_mounted = false;\n        _keyboard_dev_addr = DEV_ADDR_NONE;\n        _keyboard_instance = 0;\n        _keyboard_host_state = GamepadState{};\n    }\n    if ( _mouse_host_mounted == true && _mouse_dev_addr == dev_addr ) {\n        Gamepad *gamepad = Storage::getInstance().GetGamepad();\n        gamepad->auxState.sensors.mouse.enabled = false;\n        _mouse_host_mounted = false;\n        _mouse_dev_addr = DEV_ADDR_NONE;\n        _mouse_instance = 0;\n        _mouse_host_state = GamepadState{};\n        mouseAccumX = 0;\n        mouseAccumY = 0;\n        smoothMouseX = 0.0f;\n        smoothMouseY = 0.0f;\n        mouseRightHeld = false;\n    }\n}\n""",
    "unmount",
)

start = s.index("void KeyboardHostListener::preprocess_report()")
end = s.index("// convert hid keycode", start)
s = s[:start] + """void KeyboardHostListener::resetKeyboardState()\n{\n  _keyboard_host_state.dpad = 0;\n  _keyboard_host_state.buttons = 0;\n  _keyboard_host_state.lt = 0;\n  _keyboard_host_state.rt = 0;\n}\n\n""" + s[end:]
s = replace_once(
    s,
    "  preprocess_report();\n\n  // make this 13 instead of 7",
    "  resetKeyboardState();\n\n  // make this 13 instead of 7",
    "keyboard state reset call",
)

start = s.index("uint16_t KeyboardHostListener::scaleMouseToJoystick(")
s = s[:start] + """float KeyboardHostListener::smoothMouseDelta(int32_t delta, float &previous) {\n  if (delta == 0) {\n    previous = 0.0f;\n    return 0.0f;\n  }\n  previous = (1.0f - FPS_SMOOTHING_KEEP) * static_cast<float>(delta)\n           + FPS_SMOOTHING_KEEP * previous;\n  return previous;\n}\n\nfloat KeyboardHostListener::shapeMousePercent(float delta, bool adsActive) const {\n  if (std::fabs(delta) < 1.0e-6f) {\n    return 0.0f;\n  }\n\n  // Existing Web Config sensitivity is divided by 10 in setup().\n  // Sensitivity 30 therefore reproduces the Python sensitivity 3.0.\n  const float linearPercent = std::min(100.0f, std::fabs(delta) * mouseSensitivityScale);\n  const float normalized = linearPercent / 100.0f;\n  const float curved = std::pow(normalized, FPS_CURVE_GAMMA);\n\n  float magnitude = FPS_MIN_OUTPUT + (100.0f - FPS_MIN_OUTPUT) * curved;\n  if (adsActive) {\n    magnitude = FPS_MIN_OUTPUT + (magnitude - FPS_MIN_OUTPUT) * FPS_ADS_MULTIPLIER;\n  }\n  magnitude = std::clamp(magnitude, FPS_MIN_OUTPUT, 100.0f);\n  magnitude = std::round(magnitude);\n  return delta > 0.0f ? magnitude : -magnitude;\n}\n\nuint16_t KeyboardHostListener::percentToJoystick(float signedPercent) const {\n  const float clamped = std::clamp(signedPercent, -100.0f, 100.0f);\n  const int32_t percent = static_cast<int32_t>(std::round(std::fabs(clamped)));\n  int32_t result = joystickMid;\n  if (clamped > 0.0f) {\n    const int32_t span = GAMEPAD_JOYSTICK_MAX_I32 - joystickMid;\n    result += (span * percent + 50) / 100;\n  } else if (clamped < 0.0f) {\n    const int32_t span = joystickMid - GAMEPAD_JOYSTICK_MIN_I32;\n    result -= (span * percent + 50) / 100;\n  }\n  return static_cast<uint16_t>(std::clamp(result, GAMEPAD_JOYSTICK_MIN_I32, GAMEPAD_JOYSTICK_MAX_I32));\n}\n\nvoid KeyboardHostListener::updateFpsAim() {\n  if (mouseMovementMode == MOUSE_MOVEMENT_NONE) {\n    return;\n  }\n\n  const uint32_t now = time_us_32();\n  if (static_cast<int32_t>(now - nextAimUpdateUs) < 0) {\n    return;\n  }\n  nextAimUpdateUs += FPS_AIM_PERIOD_US;\n  if (static_cast<int32_t>(now - nextAimUpdateUs) > static_cast<int32_t>(FPS_AIM_PERIOD_US * 4)) {\n    nextAimUpdateUs = now + FPS_AIM_PERIOD_US;\n  }\n\n  const int32_t dx = mouseAccumX;\n  const int32_t dy = mouseAccumY;\n  mouseAccumX = 0;\n  mouseAccumY = 0;\n\n  const float smoothX = smoothMouseDelta(dx, smoothMouseX);\n  const float smoothY = smoothMouseDelta(dy, smoothMouseY);\n  const bool adsActive = mouseRightHeld;\n  const float xPercent = shapeMousePercent(smoothX, adsActive);\n  const float yPercent = shapeMousePercent(smoothY, adsActive);\n\n  if (mouseMovementMode == MOUSE_MOVEMENT_LEFT_ANALOG) {\n    _mouse_host_state.lx = percentToJoystick(xPercent);\n    _mouse_host_state.ly = percentToJoystick(yPercent);\n  } else if (mouseMovementMode == MOUSE_MOVEMENT_RIGHT_ANALOG) {\n    _mouse_host_state.rx = percentToJoystick(xPercent);\n    _mouse_host_state.ry = percentToJoystick(yPercent);\n  }\n}\n\nvoid KeyboardHostListener::process_mouse_report(uint8_t dev_addr, hid_mouse_report_t const * report)\n{\n  _mouse_host_state.buttons = 0;\n  _mouse_host_state.lt = 0;\n  _mouse_host_state.rt = 0;\n\n  _mouse_host_state.buttons |=\n      (report->buttons & MOUSE_BUTTON_LEFT   ? mouseLeftMapping : 0)\n    | (report->buttons & MOUSE_BUTTON_MIDDLE ? mouseMiddleMapping : 0)\n    | (report->buttons & MOUSE_BUTTON_RIGHT  ? mouseRightMapping : 0);\n\n  mouseRightHeld = (report->buttons & MOUSE_BUTTON_RIGHT) != 0;\n  mouseX = report->x;\n  mouseY = report->y;\n  mouseZ = report->wheel;\n  mouseActive = true;\n\n  if (mouseMovementMode != MOUSE_MOVEMENT_NONE) {\n    mouseAccumX += static_cast<int32_t>(report->x);\n    mouseAccumY += static_cast<int32_t>(report->y);\n  }\n}\n"""
source.write_text(s)

print("Applied custom GP2040-CE patch:")
print("  CFG_TUH_HID: 8")
print("  keyboard/mouse state: independent")
print("  aim: 120 Hz, floor=9, gamma=1.6, smoothing=0.25, ADS=0.40")
print("  sensitivity: existing Web Config value / 10 (set 30 for 3.0)")
