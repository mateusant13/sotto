import onnxruntime_genai as og
import onnxruntime as ort
import os
import gc

model_dir = r'H:/sotto/worker/models/nemotron-3.5-asr-streaming-0.6b-int8'
m = og.Model(model_dir)

print('=== og.Model inspection ===')
print(f'Model type: {type(m)}')

# Look for any attributes that might be sessions
print('\\nScanning for session-like objects...')
session_attrs = []

def check_for_sessions(obj, name=''):
    """Recursively check objects for session-like properties"""
    if hasattr(obj, 'run') and hasattr(obj, 'get_inputs') and hasattr(obj, 'get_outputs'):
        session_attrs.append((name, obj, type(obj)))
        return
    
    # Check common container types
    if isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj):
            check_for_sessions(item, f'{name}[{i}]')
    elif isinstance(obj, dict):
        for k, v in obj.items():
            check_for_sessions(v, f'{name}.{k}')
    elif hasattr(obj, '__dict__') and not name.startswith('__'):
        try:
            for attr_name in dir(obj):
                if not attr_name.startswith('_') or attr_name in ['_enc', '_dec', '_joint']:
                    try:
                        attr_val = getattr(obj, attr_name)
                        check_for_sessions(attr_val, f'{name}.{attr_name}')
                    except:
                        pass
        except:
            pass

# Start with the model object
check_for_sessions(m, 'm')

if session_attrs:
    print(f'Found {len(session_attrs)} session-like objects:')
    for name, obj, obj_type in session_attrs:
        print(f'  {name}: {obj_type}')
        try:
            inputs = obj.get_inputs()
            print(f'    Inputs: {[x.name for x in inputs]}')
        except Exception as e:
            print(f'    Could not get inputs: {e}')
        try:
            outputs = obj.get_outputs()
            print(f'    Outputs: {[x.name for x in outputs]}')
        except Exception as e:
            print(f'    Could not get outputs: {e}')
else:
    print('No session-like objects found in og.Model')

# Now manually load sessions for comparison
print('\\n=== Manual loading for comparison ===')
so = ort.SessionOptions()
so.log_severity_level = 3
try:
    so.intra_op_num_threads = int(os.environ.get('OMP_NUM_THREADS', '8'))
except:
    pass
so.inter_op_num_threads = 1

providers = ['CPUExecutionProvider']

enc_path = os.path.join(model_dir, 'encoder.onnx')
dec_path = os.path.join(model_dir, 'decoder.onnx')
joint_path = os.path.join(model_dir, 'joint.onnx')

enc = ort.InferenceSession(enc_path, so, providers=providers)
dec = ort.InferenceSession(dec_path, so, providers=providers)
joint = ort.InferenceSession(joint_path, so, providers=providers)

print(f'Manual encoder: {type(enc)}')
print(f'Manual decoder: {type(dec)}')
print(f'Manual joint: {type(joint)}')

# Check if any found sessions match the manual ones
print('\\nChecking for matches...')
matches = []
for name, obj, obj_type in session_attrs:
    if obj is enc:
        matches.append((name, 'encoder'))
    elif obj is dec:
        matches.append((name, 'decoder'))
    elif obj is joint:
        matches.append((name, 'joint'))

if matches:
    print('Found matches:')
    for name, session_type in matches:
        print(f'  {name} matches manual {session_type}')
else:
    print('No direct matches found between og.Model internals and manual loading')
    
    # Let's check if the sessions have the same structure
    print('\\nChecking structural equivalence...')
    for name, obj, obj_type in session_attrs:
        try:
            if hasattr(obj, 'get_inputs') and hasattr(enc, 'get_inputs'):
                if obj.get_inputs() == enc.get_inputs() and obj.get_outputs() == enc.get_outputs():
                    print(f'  {name} has same I/O as manual encoder')
                if obj.get_inputs() == dec.get_inputs() and obj.get_outputs() == dec.get_outputs():
                    print(f'  {name} has same I/O as manual decoder')
                if obj.get_inputs() == joint.get_inputs() and obj.get_outputs() == joint.get_outputs():
                    print(f'  {name} has same I/O as manual joint')
        except:
            pass

# Clean up
del enc, dec, joint