from pathlib import Path

# Patch GP2040-CE main @ b136ec9250c2fd2f9734467c3a3872378aa29f62
# for RP2040 Advanced Breakout Board USB Passthrough.

# 1) More HID host interfaces for composite keyboards/mice.
tusb = Path('headers/tusb_config.h')
text = tusb.read_text()
old = '#define CFG_TUH_HID 4'
assert old in text, 'CFG_TUH_HID definition not found'
tusb.write_text(text.replace(old, '#define CFG_TUH_HID 8', 1))

# 2) Split keyboard/mouse states and add the NUXBT-style FPS curve.
header = Path('headers/addons/keyboard_host_listener.h')
h = header.read_text()
old = '''    uint8_t getKeycodeFromModifier(uint8_t modifier);\n    void preprocess_report();\n    void process_kbd_report(uint8_t dev_addr, hid_keyboard_report_t const *report);\n    void process_mouse_report(uint8_t dev_addr, hid_mouse_report_t const *report);\n    uint16_t scaleMouseToJoystick(int8_t mouseVal);\n'''
new = '''    uint8_t getKeycodeFromModifier(uint8_t modifier);\n    void resetKeyboardState();\n    void process_kbd_report(uint8_t dev_addr, hid_keyboard_report_t const *report);\n    void process_mouse_report(uint8_t dev_addr, hid_mouse_report_t const *report);\n    void updateFpsAim();\n    float smoothMouseDelta(int32_t delta, float &previous);\n    float shapeMousePercent(float delta, bool adsActive) const;\n    uint16_t percentToJoystick(float signedPercent) const;\n'''
assert old in h, 'keyboard host method block not found'
h = h.replace(old, new, 1)
old = '    GamepadState _keyboard_host_state;\n'
new = '    GamepadState _keyboard_host_state;\n    GamepadState _mouse_host_state;\n'
assert old in h
h = h.replace(old, new, 1)
old = '    bool mouseActive;\n'
new = '''    bool mouseActive;\n    int32_t mouseAccumX;\n    int32_t mouseAccumY;\n    float smoothMouseX;\n    float smoothMouseY;\n    bool mouseRightHeld;\n    uint32_t nextAimUpdateUs;\n'''
assert old in h
h = h.replace(old, new, 1)
header.write_text(h)

source = Path('src/addons/keyboard_host_listener.cpp')
s = source.read_text()
s = s.replace('#include <algorithm>\n', '#include <algorithm>\n#include <cmath>\n#include "pico/time.h"\n', 1)
marker = '#define GAMEPAD_JOYSTICK_MAX_I32 static_cast<int32_t>(GAMEPAD_JOYSTICK_MAX)\n'
constants = '''#define GAMEPAD_JOYSTICK_MAX_I32 static_cast<int32_t>(GAMEPAD_JOYSTICK_MAX)\n\nnamespace {\nconstexpr float FPS_MIN_OUTPUT = 9.0f;\nconstexpr float FPS_CURVE_GAMMA = 1.6f;\nconstexpr float FPS_SMOOTHING_KEEP = 0.25f;\nconstexpr float FPS_ADS_MULTIPLIER = 0.40f;\nconstexpr uint32_t FPS_AIM_PERIOD_US = 8333; // ~120 Hz\n}\n'''
assert marker in s
s = s.replace(marker, constants, 1)

old = '''  mouseX = 0;\n  mouseY = 0;\n  mouseZ = 0;\n  mouseActive = false;\n}\n'''
new = '''  mouseX = 0;\n  mouseY = 0;\n  mouseZ = 0;\n  mouseActive = false;\n  mouseAccumX = 0;\n  mouseAccumY = 0;\n  smoothMouseX = 0.0f;\n  smoothMouseY = 0.0f;\n  mouseRightHeld = false;\n  nextAimUpdateUs = time_us_32() + FPS_AIM_PERIOD_US;\n  _keyboard_host_state = GamepadState{};\n  _mouse_host_state = GamepadState{};\n}\n'''
assert old in s
s = s.replace(old, new, 1)

start = s.index('void KeyboardHostListener::process() {')
end = s.index('void KeyboardHostListener::mount(', start)
process_impl = '''void KeyboardHostListener::process() {\n  Gamepad *gamepad = Storage::getInstance().GetGamepad();\n\n  if (_keyboard_host_mounted) {\n    gamepad->state.dpad |= _keyboard_host_state.dpad;\n    gamepad->state.buttons |= _keyboard_host_state.buttons;\n    if (!gamepad->hasAnalogTriggers) {\n      gamepad->state.lt |= _keyboard_host_state.lt;\n      gamepad->state.rt |= _keyboard_host_state.rt;\n    }\n  }\n\n  if (_mouse_host_mounted) {\n    updateFpsAim();\n    gamepad->state.buttons |= _mouse_host_state.buttons;\n    if (!gamepad->hasAnalogTriggers) {\n      gamepad->state.lt |= _mouse_host_state.lt;\n      gamepad->state.rt |= _mouse_host_state.rt;\n    }\n    if (mouseMovementMode == MOUSE_MOVEMENT_LEFT_ANALOG) {\n      gamepad->state.lx = _mouse_host_state.lx;\n      gamepad->state.ly = _mouse_host_state.ly;\n    } else if (mouseMovementMode == MOUSE_MOVEMENT_RIGHT_ANALOG) {\n      gamepad->state.rx = _mouse_host_state.rx;\n      gamepad->state.ry = _mouse_host_state.ry;\n    }\n\n    gamepad->auxState.sensors.mouse.active = mouseActive;\n    if (mouseActive) {\n      gamepad->auxState.sensors.mouse.enabled = true;\n      gamepad->auxState.sensors.mouse.x = mouseX;\n      gamepad->auxState.sensors.mouse.y = mouseY;\n      gamepad->auxState.sensors.mouse.z = mouseZ;\n      mouseActive = false;\n    }\n  }\n}\n\n'''
s = s[:start] + process_impl + s[end:]

old = '''void KeyboardHostListener::unmount(uint8_t dev_addr) {\n    if ( _keyboard_host_mounted == true && _keyboard_dev_addr == dev_addr ) {\n        _keyboard_host_mounted = false;\n        _keyboard_dev_addr = DEV_ADDR_NONE;\n        _keyboard_instance = 0;\n    } else if ( _mouse_host_mounted == true && _mouse_dev_addr == dev_addr ) {\n        Gamepad *gamepad = Storage::getInstance().GetGamepad();\n        gamepad->auxState.sensors.mouse.enabled = false;\n        _mouse_host_mounted = false;\n        _mouse_dev_addr = DEV_ADDR_NONE;\n        _mouse_instance = 0;\n    }\n}\n'''
new = '''void KeyboardHostListener::unmount(uint8_t dev_addr) {\n    if (_keyboard_host_mounted && _keyboard_dev_addr == dev_addr) {\n        _keyboard_host_mounted = false;\n        _keyboard_dev_addr = DEV_ADDR_NONE;\n        _keyboard_instance = 0;\n        _keyboard_host_state = GamepadState{};\n    }\n    if (_mouse_host_mounted && _mouse_dev_addr == dev_addr) {\n        Gamepad *gamepad = Storage::getInstance().GetGamepad();\n        gamepad->auxState.sensors.mouse.enabled = false;\n        _mouse_host_mounted = false;\n        _mouse_dev_addr = DEV_ADDR_NONE;\n        _mouse_instance = 0;\n        _mouse_host_state = GamepadState{};\n        mouseAccumX = 0;\n        mouseAccumY = 0;\n        smoothMouseX = 0.0f;\n        smoothMouseY = 0.0f;\n        mouseRightHeld = false;\n    }\n}\n'''
assert old in s
s = s.replace(old, new, 1)

start = s.index('void KeyboardHostListener::preprocess_report()')
end = s.index('// convert hid keycode', start)
reset_impl = '''void KeyboardHostListener::resetKeyboardState()\n{\n  _keyboard_host_state.dpad = 0;\n  _keyboard_host_state.buttons = 0;\n  _keyboard_host_state.lt = 0;\n  _keyboard_host_state.rt = 0;\n}\n\n'''
s = s[:start] + reset_impl + s[end:]
s = s.replace('  preprocess_report();\n  // move this preprocess dpad reset only to kbd_report (so as to not have it run on mouse input, by Fran89)\n  _keyboard_host_state.dpad = 0;\n', '  resetKeyboardState();\n', 1)

start = s.index('uint16_t KeyboardHostListener::scaleMouseToJoystick(')
replacement = '''float KeyboardHostListener::smoothMouseDelta(int32_t delta, float &previous) {\n  if (delta == 0) {\n    previous = 0.0f;\n    return 0.0f;\n  }\n  previous = (1.0f - FPS_SMOOTHING_KEEP) * static_cast<float>(delta) + FPS_SMOOTHING_KEEP * previous;\n  return previous;\n}\n\nfloat KeyboardHostListener::shapeMousePercent(float delta, bool adsActive) const {\n  if (std::fabs(delta) < 1.0e-6f) return 0.0f;\n  const float linearPercent = std::min(100.0f, std::fabs(delta) * mouseSensitivityScale);\n  const float curved = std::pow(linearPercent / 100.0f, FPS_CURVE_GAMMA);\n  float magnitude = FPS_MIN_OUTPUT + (100.0f - FPS_MIN_OUTPUT) * curved;\n  if (adsActive) magnitude = FPS_MIN_OUTPUT + (magnitude - FPS_MIN_OUTPUT) * FPS_ADS_MULTIPLIER;\n  magnitude = std::clamp(magnitude, FPS_MIN_OUTPUT, 100.0f);\n  magnitude = std::round(magnitude);\n  return delta > 0.0f ? magnitude : -magnitude;\n}\n\nuint16_t KeyboardHostListener::percentToJoystick(float signedPercent) const {\n  const float clamped = std::clamp(signedPercent, -100.0f, 100.0f);\n  const int32_t percent = static_cast<int32_t>(std::round(std::fabs(clamped)));\n  int32_t result = joystickMid;\n  if (clamped > 0.0f) {\n    result += ((GAMEPAD_JOYSTICK_MAX_I32 - joystickMid) * percent + 50) / 100;\n  } else if (clamped < 0.0f) {\n    result -= ((joystickMid - GAMEPAD_JOYSTICK_MIN_I32) * percent + 50) / 100;\n  }\n  return static_cast<uint16_t>(std::clamp(result, GAMEPAD_JOYSTICK_MIN_I32, GAMEPAD_JOYSTICK_MAX_I32));\n}\n\nvoid KeyboardHostListener::updateFpsAim() {\n  if (mouseMovementMode == MOUSE_MOVEMENT_NONE) return;\n  const uint32_t now = time_us_32();\n  if (static_cast<int32_t>(now - nextAimUpdateUs) < 0) return;\n  nextAimUpdateUs += FPS_AIM_PERIOD_US;\n  if (static_cast<int32_t>(now - nextAimUpdateUs) > static_cast<int32_t>(FPS_AIM_PERIOD_US * 4)) {\n    nextAimUpdateUs = now + FPS_AIM_PERIOD_US;\n  }\n\n  const int32_t dx = mouseAccumX;\n  const int32_t dy = mouseAccumY;\n  mouseAccumX = 0;\n  mouseAccumY = 0;\n  const float sx = smoothMouseDelta(dx, smoothMouseX);\n  const float sy = smoothMouseDelta(dy, smoothMouseY);\n  const float xp = shapeMousePercent(sx, mouseRightHeld);\n  const float yp = shapeMousePercent(sy, mouseRightHeld);\n\n  if (mouseMovementMode == MOUSE_MOVEMENT_LEFT_ANALOG) {\n    _mouse_host_state.lx = percentToJoystick(xp);\n    _mouse_host_state.ly = percentToJoystick(yp);\n  } else if (mouseMovementMode == MOUSE_MOVEMENT_RIGHT_ANALOG) {\n    _mouse_host_state.rx = percentToJoystick(xp);\n    _mouse_host_state.ry = percentToJoystick(yp);\n  }\n}\n\nvoid KeyboardHostListener::process_mouse_report(uint8_t dev_addr, hid_mouse_report_t const * report)\n{\n  _mouse_host_state.buttons = 0;\n  _mouse_host_state.lt = 0;\n  _mouse_host_state.rt = 0;\n  _mouse_host_state.buttons |=\n      (report->buttons & MOUSE_BUTTON_LEFT   ? mouseLeftMapping : 0)\n    | (report->buttons & MOUSE_BUTTON_MIDDLE ? mouseMiddleMapping : 0)\n    | (report->buttons & MOUSE_BUTTON_RIGHT  ? mouseRightMapping : 0);\n  mouseRightHeld = (report->buttons & MOUSE_BUTTON_RIGHT) != 0;\n  mouseX = report->x;\n  mouseY = report->y;\n  mouseZ = report->wheel;\n  mouseActive = true;\n  if (mouseMovementMode != MOUSE_MOVEMENT_NONE) {\n    mouseAccumX += static_cast<int32_t>(report->x);\n    mouseAccumY += static_cast<int32_t>(report->y);\n  }\n}\n'''
s = s[:start] + replacement
source.write_text(s)

print('Applied GP2040 main patch: HID=8, split keyboard/mouse state, FPS curve 3.0/9/1.6/0.25/0.40 @120Hz')
