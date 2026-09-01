from pathlib import Path

# This patch runs AFTER gp2040_main_fps_patch.py against
# GP2040-CE b136ec9250c2fd2f9734467c3a3872378aa29f62.
# It exposes the previously hard-coded FPS mouse curve values in Web Config.

# 1) Persist tunable values in KeyboardHostOptions.
proto = Path('proto/config.proto')
p = proto.read_text()
old = '''    optional uint32 mouseSensitivity = 8;\n    optional MouseMovementMode movementMode = 9;\n'''
new = '''    optional uint32 mouseSensitivity = 8;\n    optional MouseMovementMode movementMode = 9;\n    optional uint32 mouseMinOutput = 10 [default = 9];\n    optional uint32 mouseGamma = 11 [default = 160];\n    optional uint32 mouseSmoothing = 12 [default = 25];\n    optional uint32 mouseAdsMultiplier = 13 [default = 40];\n'''
assert old in p, 'KeyboardHostOptions proto block not found'
proto.write_text(p.replace(old, new, 1))

# 2) Add runtime fields to the keyboard/mouse host listener.
header = Path('headers/addons/keyboard_host_listener.h')
h = header.read_text()
old = '''    bool mouseRightHeld;\n    uint32_t nextAimUpdateUs;\n'''
new = '''    bool mouseRightHeld;\n    uint32_t nextAimUpdateUs;\n    float mouseMinOutput;\n    float mouseGamma;\n    float mouseSmoothingKeep;\n    float mouseAdsMultiplier;\n'''
assert old in h, 'FPS runtime member block not found'
header.write_text(h.replace(old, new, 1))

# 3) Replace hard-coded curve values with stored Web Config values.
source = Path('src/addons/keyboard_host_listener.cpp')
s = source.read_text()
old = '''namespace {\nconstexpr float FPS_MIN_OUTPUT = 9.0f;\nconstexpr float FPS_CURVE_GAMMA = 1.6f;\nconstexpr float FPS_SMOOTHING_KEEP = 0.25f;\nconstexpr float FPS_ADS_MULTIPLIER = 0.40f;\nconstexpr uint32_t FPS_AIM_PERIOD_US = 8333; // ~120 Hz\n}\n'''
new = '''namespace {\nconstexpr uint32_t FPS_AIM_PERIOD_US = 8333; // ~120 Hz\n}\n'''
assert old in s, 'hard-coded FPS constants block not found'
s = s.replace(old, new, 1)

old = '''  mouseSensitivityScale = mouseSensitivity / 10.0f;\n  mouseResetMS = 16;\n'''
new = '''  mouseSensitivityScale = mouseSensitivity / 10.0f;\n  mouseMinOutput = std::clamp(static_cast<float>(keyboardHostOptions.mouseMinOutput), 0.0f, 40.0f);\n  mouseGamma = std::clamp(static_cast<float>(keyboardHostOptions.mouseGamma) / 100.0f, 0.50f, 2.50f);\n  mouseSmoothingKeep = std::clamp(static_cast<float>(keyboardHostOptions.mouseSmoothing) / 100.0f, 0.0f, 0.90f);\n  mouseAdsMultiplier = std::clamp(static_cast<float>(keyboardHostOptions.mouseAdsMultiplier) / 100.0f, 0.10f, 1.0f);\n  mouseResetMS = 16;\n'''
assert old in s, 'mouse sensitivity setup block not found'
s = s.replace(old, new, 1)

s = s.replace('FPS_SMOOTHING_KEEP', 'mouseSmoothingKeep')
s = s.replace('FPS_CURVE_GAMMA', 'mouseGamma')
s = s.replace('FPS_MIN_OUTPUT', 'mouseMinOutput')
s = s.replace('FPS_ADS_MULTIPLIER', 'mouseAdsMultiplier')
assert 'FPS_MIN_OUTPUT' not in s
assert 'FPS_CURVE_GAMMA' not in s
assert 'FPS_SMOOTHING_KEEP' not in s
assert 'FPS_ADS_MULTIPLIER' not in s
source.write_text(s)

# 4) Save/load the new values through the firmware Web Config JSON API.
webconfig = Path('src/webconfig.cpp')
w = webconfig.read_text()
old = '''    docToValue(keyboardHostOptions.mouseRight, doc, "keyboardHostMouseRight");\n    docToValue(keyboardHostOptions.mouseSensitivity, doc, "keyboardHostMouseSensitivity");\n    docToValue(keyboardHostOptions.movementMode, doc, "keyboardHostMouseMovement");\n'''
new = '''    docToValue(keyboardHostOptions.mouseRight, doc, "keyboardHostMouseRight");\n    docToValue(keyboardHostOptions.mouseSensitivity, doc, "keyboardHostMouseSensitivity");\n    docToValue(keyboardHostOptions.movementMode, doc, "keyboardHostMouseMovement");\n    docToValue(keyboardHostOptions.mouseMinOutput, doc, "keyboardHostMouseMinOutput");\n    docToValue(keyboardHostOptions.mouseGamma, doc, "keyboardHostMouseGamma");\n    docToValue(keyboardHostOptions.mouseSmoothing, doc, "keyboardHostMouseSmoothing");\n    docToValue(keyboardHostOptions.mouseAdsMultiplier, doc, "keyboardHostMouseAdsMultiplier");\n'''
assert old in w, 'Web Config save block not found'
w = w.replace(old, new, 1)
old = '''    writeDoc(doc, "keyboardHostMouseRight", keyboardHostOptions.mouseRight);\n    writeDoc(doc, "keyboardHostMouseSensitivity", keyboardHostOptions.mouseSensitivity);\n    writeDoc(doc, "keyboardHostMouseMovement", keyboardHostOptions.movementMode);\n'''
new = '''    writeDoc(doc, "keyboardHostMouseRight", keyboardHostOptions.mouseRight);\n    writeDoc(doc, "keyboardHostMouseSensitivity", keyboardHostOptions.mouseSensitivity);\n    writeDoc(doc, "keyboardHostMouseMovement", keyboardHostOptions.movementMode);\n    writeDoc(doc, "keyboardHostMouseMinOutput", keyboardHostOptions.mouseMinOutput);\n    writeDoc(doc, "keyboardHostMouseGamma", keyboardHostOptions.mouseGamma);\n    writeDoc(doc, "keyboardHostMouseSmoothing", keyboardHostOptions.mouseSmoothing);\n    writeDoc(doc, "keyboardHostMouseAdsMultiplier", keyboardHostOptions.mouseAdsMultiplier);\n'''
assert old in w, 'Web Config load block not found'
webconfig.write_text(w.replace(old, new, 1))

# 5) Add sliders to the Keyboard/Mouse Host page.
ui = Path('www/src/Addons/Keyboard.tsx')
u = ui.read_text()
old = '''\tkeyboardHostMouseSensitivity: yup.number().required().min(1).max(100),\n\tkeyboardHostMouseMovement: yup.string().required().oneOf(['0', '1', '2']),\n'''
new = '''\tkeyboardHostMouseSensitivity: yup.number().required().min(1).max(100),\n\tkeyboardHostMouseMinOutput: yup.number().required().min(0).max(40),\n\tkeyboardHostMouseGamma: yup.number().required().min(50).max(250),\n\tkeyboardHostMouseSmoothing: yup.number().required().min(0).max(90),\n\tkeyboardHostMouseAdsMultiplier: yup.number().required().min(10).max(100),\n\tkeyboardHostMouseMovement: yup.string().required().oneOf(['0', '1', '2']),\n'''
assert old in u, 'Keyboard schema block not found'
u = u.replace(old, new, 1)
old = '''\tkeyboardHostMouseSensitivity: 0,\n\tkeyboardHostMouseMovement: 0,\n'''
new = '''\tkeyboardHostMouseSensitivity: 0,\n\tkeyboardHostMouseMinOutput: 9,\n\tkeyboardHostMouseGamma: 160,\n\tkeyboardHostMouseSmoothing: 25,\n\tkeyboardHostMouseAdsMultiplier: 40,\n\tkeyboardHostMouseMovement: 0,\n'''
assert old in u, 'Keyboard state block not found'
u = u.replace(old, new, 1)

anchor = '''\t\t\t\t\t<div className="col-sm-12 mb-2">\n\t\t\t\t\t\t<Form.Label>{`${t('AddonsConfig:keyboard-host-mouse-sensitivity')}: ${values.keyboardHostMouseSensitivity}%`}</Form.Label>\n\t\t\t\t\t\t<Form.Range\n\t\t\t\t\t\t\tname="keyboardHostMouseSensitivity"\n\t\t\t\t\t\t\tid={`keyboardHostMouseSensitivity`}\n\t\t\t\t\t\t\tmin={1}\n\t\t\t\t\t\t\tmax={100}\n\t\t\t\t\t\t\tstep={1}\n\t\t\t\t\t\t\tvalue={values.keyboardHostMouseSensitivity}\n\t\t\t\t\t\t\tonChange={handleChange}\n\t\t\t\t\t\t/>\n\t\t\t\t\t</div>\n'''
extra = anchor + '''\t\t\t\t\t<div className="col-sm-12 mb-2">\n\t\t\t\t\t\t<Form.Label>{`FPS Anti-Deadzone / Minimum Output: ${values.keyboardHostMouseMinOutput}%`}</Form.Label>\n\t\t\t\t\t\t<Form.Range\n\t\t\t\t\t\t\tname="keyboardHostMouseMinOutput"\n\t\t\t\t\t\t\tid="keyboardHostMouseMinOutput"\n\t\t\t\t\t\t\tmin={0}\n\t\t\t\t\t\t\tmax={40}\n\t\t\t\t\t\t\tstep={1}\n\t\t\t\t\t\t\tvalue={values.keyboardHostMouseMinOutput}\n\t\t\t\t\t\t\tonChange={handleChange}\n\t\t\t\t\t\t/>\n\t\t\t\t\t\t<Form.Text muted>Raise this when tiny mouse movements are swallowed by the game's stick deadzone.</Form.Text>\n\t\t\t\t\t</div>\n\t\t\t\t\t<div className="col-sm-12 mb-2">\n\t\t\t\t\t\t<Form.Label>{`FPS Response Gamma: ${(values.keyboardHostMouseGamma / 100).toFixed(2)}`}</Form.Label>\n\t\t\t\t\t\t<Form.Range\n\t\t\t\t\t\t\tname="keyboardHostMouseGamma"\n\t\t\t\t\t\t\tid="keyboardHostMouseGamma"\n\t\t\t\t\t\t\tmin={50}\n\t\t\t\t\t\t\tmax={250}\n\t\t\t\t\t\t\tstep={5}\n\t\t\t\t\t\t\tvalue={values.keyboardHostMouseGamma}\n\t\t\t\t\t\t\tonChange={handleChange}\n\t\t\t\t\t\t/>\n\t\t\t\t\t\t<Form.Text muted>Lower values make small movements more responsive; higher values give finer control near center.</Form.Text>\n\t\t\t\t\t</div>\n\t\t\t\t\t<div className="col-sm-12 mb-2">\n\t\t\t\t\t\t<Form.Label>{`FPS Smoothing: ${values.keyboardHostMouseSmoothing}%`}</Form.Label>\n\t\t\t\t\t\t<Form.Range\n\t\t\t\t\t\t\tname="keyboardHostMouseSmoothing"\n\t\t\t\t\t\t\tid="keyboardHostMouseSmoothing"\n\t\t\t\t\t\t\tmin={0}\n\t\t\t\t\t\t\tmax={90}\n\t\t\t\t\t\t\tstep={5}\n\t\t\t\t\t\t\tvalue={values.keyboardHostMouseSmoothing}\n\t\t\t\t\t\t\tonChange={handleChange}\n\t\t\t\t\t\t/>\n\t\t\t\t\t\t<Form.Text muted>0% is most immediate. Higher values retain more of the previous movement.</Form.Text>\n\t\t\t\t\t</div>\n\t\t\t\t\t<div className="col-sm-12 mb-2">\n\t\t\t\t\t\t<Form.Label>{`FPS ADS Multiplier: ${values.keyboardHostMouseAdsMultiplier}%`}</Form.Label>\n\t\t\t\t\t\t<Form.Range\n\t\t\t\t\t\t\tname="keyboardHostMouseAdsMultiplier"\n\t\t\t\t\t\t\tid="keyboardHostMouseAdsMultiplier"\n\t\t\t\t\t\t\tmin={10}\n\t\t\t\t\t\t\tmax={100}\n\t\t\t\t\t\t\tstep={5}\n\t\t\t\t\t\t\tvalue={values.keyboardHostMouseAdsMultiplier}\n\t\t\t\t\t\t\tonChange={handleChange}\n\t\t\t\t\t\t/>\n\t\t\t\t\t\t<Form.Text muted>Applied while the right mouse button is held. Minimum Output is preserved.</Form.Text>\n\t\t\t\t\t</div>\n'''
assert anchor in u, 'Mouse sensitivity UI block not found'
u = u.replace(anchor, extra, 1)
ui.write_text(u)

# 6) Keep the local Web Config mock server consistent (not required on-device, useful for UI testing).
server = Path('www/server/app.js')
sv = server.read_text()
old = '''\t\tkeyboardHostMouseSensitivity: 50,\n\t\tkeyboardHostMouseMovement: 0,\n'''
new = '''\t\tkeyboardHostMouseSensitivity: 50,\n\t\tkeyboardHostMouseMinOutput: 9,\n\t\tkeyboardHostMouseGamma: 160,\n\t\tkeyboardHostMouseSmoothing: 25,\n\t\tkeyboardHostMouseAdsMultiplier: 40,\n\t\tkeyboardHostMouseMovement: 0,\n'''
if old in sv:
    server.write_text(sv.replace(old, new, 1))

print('Applied Web Config FPS tuning: sensitivity + anti-deadzone + gamma + smoothing + ADS multiplier')
