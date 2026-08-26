# Skeptical Review: openai-kokoro-tts Repository
## Date: 2026-08-27
## Branch: review/2026-08-27-skeptical

---

## EXECUTIVE SUMMARY

**GitHub main is STALE (March 21, 2025)**. The repository contains partial ONNX implementation with broken conversion, duplicate handlers, server bugs, NO Gradio interface, and incomplete transformers support. The working ONNX+Gradio version claimed to exist on GamingPC is NOT in this repository.

---

## VERIFICATION OF CLAIMS vs REALITY

### Claim: "Working ONNX+Gradio on GamingPC"
**Reality**: 
- ✅ ONNX code exists (partially)
- ❌ NO Gradio code anywhere in repo (0 mentions, 0 files)
- ❌ Server has critical bugs (see below)

### Claim: "GitHub main still has old March 2025 .pth Docker"
**Reality**: 
- ✅ CONFIRMED: Latest commit is `17a733b` from 2025-03-21
- ✅ Dockerfile does download .pth files (lines 21-28)
- ⚠️ Dockerfile ALSO attempts ONNX conversion (lines 30-37)

---

## CRITICAL ISSUES FOUND

### 1. DUPLICATE ONNX HANDLERS (Code Smell)
Two different implementations:
- `/workspace/onnx_tts_handler.py` (root, 114 lines)
- `/workspace/openai_kokoro_tts/onnx_tts_handler.py` (package, 71 lines)

**Differences**:
- Root version: Uses `_text_to_tokens()` returning int32, has `get_voices()` method
- Package version: Different `_text_to_tokens()` returning int64, has `get_voices()` method
- Server imports from package version (line 10 in server.py)
- Root version is ORPHANED and unused

**Recommendation**: DELETE `/workspace/onnx_tts_handler.py`

---

### 2. SERVER BUG: Type Mismatch (Critical)

**File**: `openai_kokoro_tts/server.py` lines 96-99

```python
audio = tts_handler.generate_speech(text=text, voice=voice, speed=speed)
audio_bytes = process_audio_output(audio)
```

**Problem**: 
- `generate_speech()` in `openai_kokoro_tts/onnx_tts_handler.py` returns a **file path** (line 60)
- `process_audio_output()` expects a **numpy array** (line 38)
- This WILL crash at runtime

**Root cause**: The two ONNX handlers have different return types:
- Package handler (used by server): Returns file path string
- Root handler: Returns numpy array (intended)

**Fix needed**: Handler should return raw audio data, not file path

---

### 3. BROKEN ONNX CONVERSION (Docker Build Failure Risk)

**File**: `openai_kokoro_tts/convert_to_onnx.py` lines 18-34

**Problems**:
1. Assumes .pth contains a dict with key `bert_encoder` (line 25)
2. Commented out alternatives for `decoder` and `predictor` (lines 26-27)
3. No validation that extracted object is actually a torch.nn.Module
4. Hardcoded input shapes may not match actual model (lines 38-40)
5. **Dockerfile runs this conversion TWICE** (lines 36-37) - redundant

**Evidence of uncertainty**: The commented-out lines show developer didn't know structure

**Likely result**: Docker build fails at ONNX conversion step

---

### 4. INCOMPLETE TRANSFORMERS HANDLER

**File**: `openai_kokoro_tts/transformers_tts_handler.py`

**Status**: Mock/stub implementation
- Line 75: `_mock_text_to_audio()` generates random noise, not real speech
- Line 34: Tries to load non-existent model `kokoro/kokoro-transformers`
- Will fail immediately if USE_ONNX=false

**README claims**: "Transformers GPU inference" (line 278)
**Reality**: Checkbox is unchecked, feature doesn't work

---

### 5. NO GRADIO INTERFACE

**Search results**: 0 files, 0 mentions, 0 imports

**GamingPC claim verification**: Cannot verify what exists on GamingPC

**Impact**: No web UI for testing/demo, only API endpoint

---

### 6. INCONSISTENT VOICE SUPPORT

**ONNX handler** (openai_kokoro_tts/onnx_tts_handler.py line 12):
```python
self.valid_voices = ["af_bella", "af_sky"]
```

**Root ONNX handler** (onnx_tts_handler.py line 19):
```python
self.valid_voices = ["af_bella", "af_sky"]
```

**README example** (lines 228-240):
Lists 11 voices including `af_nicole`, `am_adam`, `bf_emma`, etc.

**Verdict**: README is misleading. Only 2 voices actually work.

---

### 7. ENVIRONMENT VARIABLE CONFUSION

Different default paths across files:

| File | Variable | Default Value |
|------|----------|---------------|
| .env.example | ONNX_MODEL_PATH | Not set |
| .env.example | MODEL_PATH | ./models/kokoro/kokoro-v0_19.pth |
| onnx_tts_handler.py (root) | ONNX_MODEL_PATH | models/kokoro/kokoro-v0_19.onnx |
| onnx_tts_handler.py (package) | ONNX_MODEL_PATH | models/kokoro/kokoro.onnx |
| convert_to_onnx.py | Output filename | kokoro.onnx (no version) |

**Result**: Path mismatches will cause file-not-found errors

---

## FILE INVENTORY

### Python Code (11 files)
- ✅ `openai_kokoro_tts/server.py` - Flask API (has bugs)
- ⚠️ `openai_kokoro_tts/onnx_tts_handler.py` - Active ONNX handler (wrong return type)
- ❌ `onnx_tts_handler.py` - Duplicate, orphaned, DELETE
- ⚠️ `openai_kokoro_tts/convert_to_onnx.py` - Broken conversion script
- ⚠️ `openai_kokoro_tts/transformers_tts_handler.py` - Mock/incomplete
- ✅ `openai_kokoro_tts/utils.py` - Working utilities
- ✅ `openai_kokoro_tts/simple_audio_converter.py` - Appears functional
- ✅ `openai_kokoro_tts/tts_handler.py` - Base class
- ✅ `cli_local_inference.py` - CLI tool
- ✅ `tests/test_onnx_tts_handler.py` - Unit tests

### Docker/Config (4 files)
- ⚠️ `Dockerfile` - Has redundant ONNX conversion (lines 36-37)
- ✅ `docker-compose.yml` - Standard config
- ✅ `docker-compose.override.yml.example` - NVIDIA GPU config
- ✅ `.env.example` - Example environment

### Documentation (3 files)
- ⚠️ `README.md` - Misleading claims about features
- ✅ `LICENSE` - MIT license
- ✅ `.github/workflows/python-pytest.yml` - CI config

### Setup Scripts (2 files)
- ✅ `setup_models.sh` - Linux setup
- ✅ `setup_models.ps1` - Windows setup

---

## RANKED RECOMMENDATIONS

### PRIORITY 1: MUST FIX (Blockers)

1. **FIX SERVER BUG** - Make ONNX handler return numpy array, not file path
   - Edit `openai_kokoro_tts/onnx_tts_handler.py` lines 29-63
   - Remove file writing, return raw audio data
   
2. **DELETE DUPLICATE** - Remove `/workspace/onnx_tts_handler.py`
   - Prevents confusion
   - Eliminates maintenance burden

3. **FIX DOCKERFILE** - Remove duplicate ONNX conversion line
   - Delete line 36 or 37 (identical commands)

### PRIORITY 2: SHOULD FIX (Correctness)

4. **FIX ONNX CONVERSION** - Replace hacky convert_to_onnx.py
   - Option A: Use kokoro-onnx library (already in dependencies line 19)
   - Option B: Download pre-converted .onnx files
   - Option C: Write proper conversion with model structure validation

5. **STANDARDIZE PATHS** - Consistent ONNX model filename
   - Choose either `kokoro.onnx` or `kokoro-v0_19.onnx`
   - Update all references (Dockerfile, handlers, .env.example)

6. **UPDATE README** - Correct the voice list
   - Remove claim of 11 voices
   - Document actual 2 voices supported: af_bella, af_sky
   - Add note about Gradio UI being in development

### PRIORITY 3: FEATURES TO RESTORE (From GamingPC)

7. **ADD GRADIO INTERFACE** 
   - This is the key missing piece vs GamingPC version
   - Create `openai_kokoro_tts/gradio_ui.py`
   - Add gradio to dependencies in pyproject.toml
   - Provide web UI for testing without API clients

8. **IMPLEMENT TRANSFORMERS HANDLER**
   - Replace mock implementation
   - Use actual Kokoro TTS model loading
   - Enable GPU inference option

9. **EXPAND VOICE SUPPORT**
   - Add remaining 9 voices from voices.json
   - Update handler to load voice embeddings properly

### PRIORITY 4: CLEANUP (Technical Debt)

10. **REMOVE ORPHANED FILES**
    - `cli_local_inference.py` - Uses .pth directly, bypasses ONNX
    - `debug_inference.sh` - Unclear purpose

11. **IMPROVE TESTS**
    - Add integration tests for server endpoints
    - Add Docker build tests
    - Test ONNX conversion pipeline

12. **UPDATE DEPENDENCIES**
    - Some packages may have newer versions (3 months old)
    - Audit security vulnerabilities

---

## SYNC STRATEGY: GamingPC -> GitHub

### Investigation Needed (Cannot complete without GamingPC access)

1. **Locate Gradio code on GamingPC**
   - Search for: `*.py` files with `import gradio`
   - Expected location: Probably `openai_kokoro_tts/gradio_ui.py`

2. **Check GamingPC ONNX handler**
   - Compare return type of `generate_speech()`
   - Verify if bug is fixed there

3. **Verify working ONNX conversion**
   - Is there a different convert_to_onnx.py on GamingPC?
   - Or does it download pre-converted .onnx files?

4. **Check for additional files**
   - Any new utilities?
   - Different Dockerfile?
   - Updated dependencies?

### Files to PUSH from GamingPC to GitHub (Once verified working)

| Priority | File | Reason |
|----------|------|--------|
| 1 | `openai_kokoro_tts/gradio_ui.py` | Key missing feature |
| 1 | `openai_kokoro_tts/onnx_tts_handler.py` | Fixed version (if bug is fixed) |
| 2 | `openai_kokoro_tts/convert_to_onnx.py` | If improved/working version exists |
| 2 | `Dockerfile` | If simplified/improved |
| 3 | `pyproject.toml` | If gradio dependency added |
| 3 | `README.md` | If updated with correct info |

### Files to DELETE from GitHub

| File | Reason |
|------|--------|
| `/workspace/onnx_tts_handler.py` | Duplicate, orphaned, unused |
| `cli_local_inference.py` | Bypasses ONNX, uses .pth directly - confusing |

### Configuration Changes Needed

1. **Dockerfile**: Remove duplicate line 36 or 37
2. **README.md**: Update voice list to match reality (2 voices, not 11)
3. **.env.example**: Add ONNX_MODEL_PATH with correct default
4. **pyproject.toml**: Add gradio dependency

---

## RISK ASSESSMENT

### Current State Risks

| Risk | Severity | Probability | Impact |
|------|----------|-------------|---------|
| Docker build fails at ONNX conversion | HIGH | 80% | Cannot deploy |
| Server crashes on first API call | HIGH | 95% | Service unusable |
| User expects 11 voices, gets error | MEDIUM | 70% | Bad UX |
| Transformers mode completely broken | LOW | 100% | Feature unavailable |

### Post-Fix Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| GamingPC version diverges further | MEDIUM | Push fixes immediately |
| ONNX conversion still fails | MEDIUM | Use pre-converted files |
| Performance issues with ONNX CPU | LOW | Document GPU option clearly |

---

## TEST PLAN (Before Pushing Fixes)

### Unit Tests
- [ ] `pytest tests/` passes on main
- [ ] `pytest tests/` passes on review branch

### Integration Tests
1. [ ] Docker build completes without errors
2. [ ] Container starts successfully
3. [ ] `/v1/models` endpoint returns 2 voices
4. [ ] `/v1/audio/speech` with af_bella works
5. [ ] `/v1/audio/speech` with af_sky works
6. [ ] `/v1/audio/speech` with invalid voice returns 400 error
7. [ ] API key authentication works
8. [ ] Response format wav works
9. [ ] Response format mp3 works (if conversion enabled)

### Manual Testing
- [ ] Generate 5-10 different test sentences
- [ ] Verify audio quality is acceptable
- [ ] Check for artifacts/distortion
- [ ] Measure generation time (baseline for optimization)

---

## CONCLUSION

**The repository is in a broken state**. While ONNX code exists, it has critical bugs that prevent it from running. The Gradio interface exists only on GamingPC (unverified). The README makes claims about features that don't work.

**Immediate action required**: Fix Priority 1 issues before any deployment. Then sync with GamingPC to restore missing Gradio functionality.

**Timeline estimate**: 
- Priority 1 fixes: 2-4 hours
- Priority 2 fixes: 4-6 hours
- Priority 3 features: 8-16 hours
- Priority 4 cleanup: 4-8 hours

**Recommendation**: Do NOT merge review branch. Use it as analysis only. Create separate feature branch for actual fixes.

---

## APPENDIX: COMMIT HISTORY ANALYSIS

Latest 10 commits (all from January-March 2025):

```
17a733b 2025-03-21 Update Dockerfile and onnx_tts_handler.py for ONNX model conversion and setup
1df3a3c 2025-01-20 docs: added note about PYTHONPATH
cf977be 2025-01-20 fix(python): resolve ARM-compatible torch installation
48244a8 2025-01-16 fix: restore /v1/models
dad16cf 2025-01-16 fix(CI): download models
b1b7d44 2025-01-16 fix(docker): add . to PYTHONPATH
160b38e 2025-01-16 fix: pytest tests/
1975863 2025-01-16 chore(setup): update setup_models.sh with professional comments
68e8190 2025-01-16 fix(ci): ensure pytest is installed explicitly for CI
bad1bec 2025-01-16 fix(ci): downgrade Python version to 3.11 for compatibility
```

**Observation**: Heavy activity in January 2025 (10 commits on Jan 16 alone), then nothing until March 21, then silence for 5+ months. Suggests project was abandoned or moved to GamingPC for local development.

---

## METADATA

- **Review Date**: 2026-08-27
- **Reviewer**: Cloud Agent
- **Repository**: openai-kokoro-tts
- **Branch Reviewed**: main (commit 17a733b)
- **Review Branch**: review/2026-08-27-skeptical
- **Lines of Code Analyzed**: ~2,500
- **Files Reviewed**: 20
- **Critical Bugs Found**: 2
- **Warnings**: 8
- **Recommendations**: 12
