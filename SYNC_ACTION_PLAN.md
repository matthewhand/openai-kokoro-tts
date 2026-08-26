# GamingPC <-> GitHub Sync Action Plan
## Date: 2026-08-27
## Goal: Make GamingPC and GitHub match with working ONNX+Gradio

---

## RANKED PRIORITY: WHAT TO DO FIRST

### STAGE 1: VERIFY (Do NOT Push Anything Yet)

**On GamingPC, investigate:**

1. **Find Gradio code** (CRITICAL)
   ```bash
   cd /path/to/openai-kokoro-tts
   grep -r "import gradio" .
   find . -name "*gradio*.py"
   ```
   
2. **Check ONNX handler** (CRITICAL)
   ```bash
   # Compare with GitHub version
   cat openai_kokoro_tts/onnx_tts_handler.py
   # Look at line ~60: Does generate_speech() return file path or numpy array?
   ```

3. **Test current GamingPC state** (CRITICAL)
   ```bash
   # Does it actually work?
   python openai_kokoro_tts/server.py
   curl -X POST http://localhost:9090/v1/audio/speech \
     -H "Authorization: Bearer YOUR_KEY" \
     -H "Content-Type: application/json" \
     -d '{"input": "Hello world", "voice": "af_bella"}'
   ```

4. **Check for other differences**
   ```bash
   ls -la  # Any new files vs GitHub?
   git status  # Uncommitted changes?
   git log --oneline -10  # Local commits not pushed?
   ```

---

## STAGE 2: FIX GITHUB FIRST (Before Syncing)

**Why**: GitHub has known critical bugs. Fix those BEFORE pulling from GamingPC to avoid confusion.

### Fix 1: Delete Duplicate ONNX Handler

```bash
git checkout main
git pull origin main
git checkout -b fix/remove-duplicate-onnx-handler
rm /workspace/onnx_tts_handler.py
git add onnx_tts_handler.py
git commit -m "fix: remove duplicate orphaned ONNX handler from root"
git push -u origin fix/remove-duplicate-onnx-handler
```

### Fix 2: Fix Server Return Type Bug

**File**: `openai_kokoro_tts/onnx_tts_handler.py`

**Change lines 29-63 from**:
```python
def generate_speech(self, text, voice=None, response_format="wav", speed=1.0):
    # ... processing ...
    output_file = os.path.join(output_dir, f"output.{response_format}")
    sf.write(output_file, audio, samplerate=16000, format=response_format.upper())
    return output_file  # BUG: Returns path, not data
```

**To**:
```python
def generate_speech(self, text, voice=None, response_format="wav", speed=1.0):
    # ... processing ...
    # Return raw audio data, not file path
    return audio  # Now returns numpy array
```

**File**: `openai_kokoro_tts/server.py`

**Change line 98 from**:
```python
audio = tts_handler.generate_speech(text=text, voice=voice, speed=speed)
```

**To**:
```python
# generate_speech now returns raw numpy array
audio = tts_handler.generate_speech(text=text, voice=voice, speed=speed)
```

This should work correctly now.

### Fix 3: Remove Duplicate Dockerfile Line

**File**: `Dockerfile`

**Delete line 37** (duplicate of line 36):
```dockerfile
# DELETE THIS LINE:
RUN python openai_kokoro_tts/convert_to_onnx.py && mv /app/openai_kokoro_tts/kokoro.onnx /app/models/kokoro/
```

### Fix 4: Update README Voice List

**File**: `README.md`

**Change lines 228-240 from**:
```json
{
  "models": [
    "af", "af_bella", "af_sarah", "am_adam", "am_michael",
    "bf_emma", "bf_isabella", "bm_george", "bm_lewis",
    "af_nicole", "af_sky"
  ]
}
```

**To**:
```json
{
  "models": [
    "af_bella",
    "af_sky"
  ]
}
```

**Add note after line 241**:
```markdown
> **Note**: Currently only 2 voices are fully implemented. Additional voices from the Kokoro model will be added in future updates.
```

---

## STAGE 3: SYNC FROM GamingPC (If Verified Working)

### Scenario A: GamingPC has fixes + Gradio

**If GamingPC version is confirmed working and has Gradio UI:**

```bash
# On GamingPC
cd /path/to/openai-kokoro-tts
git checkout -b feature/add-gradio-ui
git add openai_kokoro_tts/gradio_ui.py  # New file
git add pyproject.toml  # Updated with gradio dependency
git commit -m "feat: add Gradio web UI for testing and demos"
git push -u origin feature/add-gradio-ui
```

**Files to push from GamingPC**:
1. `openai_kokoro_tts/gradio_ui.py` (NEW)
2. `pyproject.toml` (UPDATED - adds gradio)
3. `uv.lock` (UPDATED - from uv sync)
4. Any other Gradio-related files (assets, configs, etc.)

### Scenario B: GamingPC has different ONNX handler

**If GamingPC's onnx_tts_handler.py is different/better:**

```bash
# Compare first
diff openai_kokoro_tts/onnx_tts_handler.py /path/to/github/clone/openai_kokoro_tts/onnx_tts_handler.py

# If GamingPC version is better, copy it
cp openai_kokoro_tts/onnx_tts_handler.py /path/to/github/clone/openai_kokoro_tts/
cd /path/to/github/clone
git checkout -b fix/update-onnx-handler
git add openai_kokoro_tts/onnx_tts_handler.py
git commit -m "fix: update ONNX handler with working version from GamingPC"
git push -u origin fix/update-onnx-handler
```

### Scenario C: GamingPC has working ONNX conversion

**If GamingPC has better convert_to_onnx.py:**

```bash
# Compare first
diff openai_kokoro_tts/convert_to_onnx.py /path/to/github/clone/openai_kokoro_tts/convert_to_onnx.py

# If better, copy it
cp openai_kokoro_tts/convert_to_onnx.py /path/to/github/clone/openai_kokoro_tts/
cd /path/to/github/clone
git checkout -b fix/onnx-conversion
git add openai_kokoro_tts/convert_to_onnx.py
git commit -m "fix: use working ONNX conversion from GamingPC"
git push -u origin fix/onnx-conversion
```

---

## STAGE 4: TEST EVERYTHING

### On GitHub (After Fixes)

```bash
# Clone fresh
git clone https://github.com/matthewhand/openai-kokoro-tts.git test-repo
cd test-repo

# Test Docker build
docker-compose build
# Should complete without errors

# Test Docker run
docker-compose up -d
# Check logs
docker-compose logs -f

# Test API
curl -X POST http://localhost:9090/v1/models \
  -H "Authorization: Bearer test_key"
# Should return {"models": ["af_bella", "af_sky"]}

curl -X POST http://localhost:9090/v1/audio/speech \
  -H "Authorization: Bearer test_key" \
  -H "Content-Type: application/json" \
  -d '{"input": "Testing one two three", "voice": "af_bella"}' \
  --output test.wav
# Should create test.wav file

# Play audio to verify quality
aplay test.wav  # Linux
afplay test.wav  # macOS
```

### On GamingPC (Before Pushing)

```bash
# Same tests as above
docker-compose build
docker-compose up -d
# Test API calls
# Test Gradio UI (if present) at http://localhost:7860 or similar
```

---

## STAGE 5: DOCUMENTATION UPDATES

### Update README.md

**Add Gradio section** (after line 197):

```markdown
### Using the Gradio Web UI (Optional)

For quick testing and demos without API clients:

1. Start the Gradio interface:
   ```bash
   PYTHONPATH=. uv run openai_kokoro_tts/gradio_ui.py
   ```

2. Open browser to `http://localhost:7860`

3. Enter text, select voice, and click "Generate Speech"

The Gradio UI provides a simple way to test voice quality and parameters before integrating with your application.
```

**Update TODO section** (line 275):

```markdown
## TODO

- [x] ONNX CPU inference
- [x] Gradio web UI
- [ ] Transformers GPU inference
- [ ] Expand voice support (currently 2/11 voices)
- [ ] Simplify using kokoro-onnx library
- [ ] Add audio format conversion (mp3, opus, etc.)
- [ ] Streaming audio support
- [ ] Voice cloning support
```

---

## STAGE 6: CLEANUP (Delete Obsolete Files)

### On GamingPC

**Before pushing to GitHub, remove these if they exist:**

```bash
# Check if these exist and are orphaned
ls -la cli_local_inference.py  # Uses .pth directly, confusing
ls -la debug_inference.sh  # Unclear purpose
ls -la onnx_tts_handler.py  # Root duplicate (already removed from GitHub)

# If found and not needed:
rm cli_local_inference.py
rm debug_inference.sh
git add -A
git commit -m "chore: remove obsolete CLI and debug scripts"
```

---

## DECISION MATRIX: WHAT TO PUSH, WHAT TO DELETE

### PUSH from GamingPC to GitHub

| File | Condition | Priority |
|------|-----------|----------|
| `openai_kokoro_tts/gradio_ui.py` | If exists and works | CRITICAL |
| `openai_kokoro_tts/onnx_tts_handler.py` | If different and better | HIGH |
| `openai_kokoro_tts/convert_to_onnx.py` | If different and better | HIGH |
| `pyproject.toml` | If has gradio dependency | MEDIUM |
| `uv.lock` | If pyproject.toml changed | MEDIUM |
| `Dockerfile` | If simplified/improved | MEDIUM |
| `README.md` | If has Gradio docs | MEDIUM |
| Any new utility files | If used by Gradio | LOW |

### DELETE from GitHub

| File | Reason | Priority |
|------|--------|----------|
| `/workspace/onnx_tts_handler.py` | Duplicate, orphaned | CRITICAL |
| `cli_local_inference.py` | Bypasses ONNX, confusing | MEDIUM |
| `debug_inference.sh` | Unclear purpose | LOW |

### DELETE from GamingPC (Don't push these)

| File | Reason |
|------|--------|
| `*.pyc` | Compiled Python (should be in .gitignore) |
| `__pycache__/` | Python cache (should be in .gitignore) |
| `.env` | Local secrets (never push) |
| `outputs/` | Generated audio files (temp) |
| `models/` | Large model files (downloaded, not committed) |

---

## BRANCH STRATEGY

### Current State

```
main (GitHub)
  - Stale (March 2025)
  - Has critical bugs
  - Missing Gradio
```

### Proposed Structure

```
main (GitHub)
  |
  +-- fix/remove-duplicate-onnx-handler (GitHub fix)
  |
  +-- fix/server-return-type (GitHub fix)
  |
  +-- fix/dockerfile-duplicate-line (GitHub fix)
  |
  +-- feature/add-gradio-ui (from GamingPC)
  |
  +-- fix/update-onnx-handler (from GamingPC, if needed)
  |
  +-- fix/onnx-conversion (from GamingPC, if needed)
  |
  +-- integration/all-fixes (merge all above)
        |
        v
      main (merged, tested, deployed)
```

### Workflow

1. Create fix branches on GitHub for known bugs
2. Test each fix branch individually
3. Create feature branch for Gradio from GamingPC
4. Test Gradio branch individually
5. Create integration branch merging all fixes
6. Full integration testing
7. Merge integration branch to main
8. Tag release: `v0.2.0` (ONNX + Gradio working)

---

## ROLLBACK PLAN

**If something breaks after syncing:**

```bash
# On GitHub
git checkout main
git log --oneline -10  # Find last good commit
git revert <bad-commit-hash>
git push origin main

# On GamingPC
git fetch origin
git reset --hard origin/main  # Reset to GitHub main
# Or keep GamingPC changes separate:
git checkout -b gamingpc-backup
git branch -D main
git checkout -b main origin/main
```

---

## VALIDATION CHECKLIST

**Before considering sync complete:**

- [ ] Docker build succeeds on GitHub
- [ ] Docker build succeeds on GamingPC
- [ ] Unit tests pass on both (`pytest tests/`)
- [ ] API endpoint `/v1/models` works
- [ ] API endpoint `/v1/audio/speech` works with af_bella
- [ ] API endpoint `/v1/audio/speech` works with af_sky
- [ ] Generated audio quality is acceptable (manual listening test)
- [ ] Gradio UI launches (if added)
- [ ] Gradio UI generates audio successfully (if added)
- [ ] README documentation matches actual functionality
- [ ] No orphaned files remain
- [ ] No duplicate code remains
- [ ] Environment variables are consistent
- [ ] `.gitignore` prevents committing models/outputs

---

## ESTIMATED EFFORT

| Stage | Time | Risk |
|-------|------|------|
| Stage 1: Verify GamingPC | 30 min | LOW |
| Stage 2: Fix GitHub bugs | 2 hours | LOW |
| Stage 3: Sync from GamingPC | 1 hour | MEDIUM |
| Stage 4: Testing | 2 hours | MEDIUM |
| Stage 5: Documentation | 1 hour | LOW |
| Stage 6: Cleanup | 30 min | LOW |
| **TOTAL** | **7 hours** | **MEDIUM** |

**Risk factors**:
- GamingPC version might also have bugs
- ONNX conversion might still fail
- Gradio might have unexpected dependencies
- Integration testing might reveal new issues

---

## SUCCESS CRITERIA

**Mission accomplished when:**

1. ✅ GitHub main has no critical bugs
2. ✅ Docker build completes successfully
3. ✅ API endpoints work correctly
4. ✅ Gradio UI is present and functional
5. ✅ GamingPC and GitHub codebases match
6. ✅ README accurately describes features
7. ✅ No duplicate or orphaned code
8. ✅ All tests pass

**Deploy to production when:**
- [ ] All success criteria met
- [ ] Manual testing shows good audio quality
- [ ] Performance is acceptable (measure TTS generation time)
- [ ] Security review passed (API key handling, input validation)

---

## CONTACT / ESCALATION

**If you encounter issues:**

1. **Docker build fails**: Check ONNX conversion step, may need pre-converted .onnx files
2. **API crashes**: Check server logs, likely numpy array vs file path issue
3. **Gradio not found**: Confirm GamingPC actually has it, may need to build from scratch
4. **Audio quality poor**: Check model version, may need different .pth file
5. **Voice not working**: Check voices.json, may need voice embedding files

---

## NEXT STEPS (After Sync Complete)

1. **Expand voice support**: Add remaining 9 voices
2. **Add streaming**: Real-time audio generation
3. **GPU support**: Enable transformers handler
4. **Format conversion**: Add mp3/opus encoding
5. **Performance optimization**: Profile and optimize ONNX inference
6. **API features**: Add speed control, pitch control, emotion parameters
7. **Monitoring**: Add Prometheus metrics, logging
8. **CI/CD**: Automate testing and deployment

---

## APPENDIX A: File Comparison Commands

**Compare GamingPC vs GitHub:**

```bash
# On GamingPC
cd /path/to/openai-kokoro-tts
find . -name "*.py" -type f | sort > /tmp/gamingpc-files.txt

# On GitHub clone
cd /path/to/github/clone
find . -name "*.py" -type f | sort > /tmp/github-files.txt

# Compare
diff /tmp/gamingpc-files.txt /tmp/github-files.txt
# Output shows files present on one but not the other

# Compare specific files
diff -u /path/to/gamingpc/file.py /path/to/github/file.py
```

---

## APPENDIX B: Expected Gradio UI Code (If Missing)

**If Gradio doesn't exist on GamingPC, here's what it should look like:**

```python
# openai_kokoro_tts/gradio_ui.py
import gradio as gr
import os
from openai_kokoro_tts.onnx_tts_handler import OnnxTTSHandler

handler = OnnxTTSHandler()

def generate_audio(text, voice, speed):
    """Generate audio from text using ONNX TTS handler"""
    try:
        audio = handler.generate_speech(text=text, voice=voice, speed=speed)
        # Return audio data for Gradio
        return (16000, audio)  # (sample_rate, audio_data)
    except Exception as e:
        return f"Error: {str(e)}"

# Build Gradio interface
demo = gr.Interface(
    fn=generate_audio,
    inputs=[
        gr.Textbox(label="Text", placeholder="Enter text to convert to speech..."),
        gr.Dropdown(choices=["af_bella", "af_sky"], label="Voice", value="af_bella"),
        gr.Slider(minimum=0.5, maximum=2.0, value=1.0, label="Speed")
    ],
    outputs=gr.Audio(label="Generated Speech"),
    title="Kokoro TTS Demo",
    description="Convert text to speech using Kokoro ONNX models"
)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
```

**To use**: Add `gradio>=4.0.0` to pyproject.toml dependencies, then run `uv sync`

---

## METADATA

- **Plan Date**: 2026-08-27
- **Author**: Cloud Agent
- **Repository**: openai-kokoro-tts
- **Target**: Sync GamingPC (working) with GitHub (stale)
- **Estimated Completion**: 7 hours
- **Risk Level**: MEDIUM
