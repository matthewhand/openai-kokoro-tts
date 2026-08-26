# QUICK REFERENCE: Critical Findings & Actions
## openai-kokoro-tts Repository Review
## Date: 2026-08-27

---

## CRITICAL BUGS (Fix Immediately)

### 🔴 BUG #1: Server Type Mismatch - WILL CRASH ON FIRST API CALL

**Location**: `openai_kokoro_tts/onnx_tts_handler.py` line 60 + `openai_kokoro_tts/server.py` line 98

**Problem**: Handler returns file path (string), server expects numpy array

**Impact**: 100% crash rate on API usage

**Fix**:
```python
# In onnx_tts_handler.py, change line 60 from:
return output_file

# To:
return audio
```

**Time**: 5 minutes

---

### 🔴 BUG #2: Duplicate Dockerfile Command

**Location**: `Dockerfile` lines 36-37

**Problem**: Same ONNX conversion runs twice

**Impact**: Wastes build time, potential race condition

**Fix**: Delete line 37

**Time**: 1 minute

---

## CRITICAL ISSUES (Requires Investigation)

### ⚠️ ISSUE #1: Missing Gradio Interface

**Claim**: Working on GamingPC

**Reality**: Not in GitHub repo (0 files found)

**Action**: Search GamingPC for `import gradio` in .py files

**Priority**: HIGH - This is the key differentiator vs GitHub

---

### ⚠️ ISSUE #2: Broken ONNX Conversion

**Location**: `openai_kokoro_tts/convert_to_onnx.py` lines 18-34

**Problem**: 
- Assumes .pth has `bert_encoder` key
- Commented out alternatives show uncertainty
- No validation
- May cause Docker build failure

**Action**: Test Docker build, if fails use pre-converted .onnx or GamingPC version

**Priority**: HIGH - Blocks deployment

---

### ⚠️ ISSUE #3: Duplicate ONNX Handler

**Locations**: 
- `/workspace/onnx_tts_handler.py` (orphaned, 114 lines)
- `/workspace/openai_kokoro_tts/onnx_tts_handler.py` (active, 71 lines)

**Problem**: Confusion, maintenance burden, server uses package version only

**Action**: Delete root version

**Priority**: MEDIUM - Prevents confusion

---

## WHAT TO PUSH FROM GamingPC

**Priority 1 (Must have)**:
- `openai_kokoro_tts/gradio_ui.py` - Missing web UI

**Priority 2 (If better than GitHub)**:
- `openai_kokoro_tts/onnx_tts_handler.py` - Check if bug is fixed
- `openai_kokoro_tts/convert_to_onnx.py` - Check if conversion works
- `pyproject.toml` - If has gradio dependency

**Priority 3 (Nice to have)**:
- `Dockerfile` - If simplified
- `README.md` - If has Gradio docs

---

## WHAT TO DELETE

**From GitHub** (now):
- `/workspace/onnx_tts_handler.py` - Duplicate
- `cli_local_inference.py` - Bypasses ONNX, confusing

**From GamingPC** (before pushing):
- `*.pyc` - Compiled Python
- `__pycache__/` - Cache
- `.env` - Secrets
- `outputs/` - Generated files
- `models/` - Downloaded, not committed

---

## MISLEADING README CLAIMS

### Claim: 11 voices available
**Reality**: Only 2 work (af_bella, af_sky)

**Fix**: Update README lines 228-240, remove 9 voices

---

### Claim: "Transformers GPU inference" 
**Reality**: Mock implementation, generates random noise

**Status**: TODO checkbox already unchecked (line 278)

---

## VERIFICATION COMMANDS

### Test Docker Build
```bash
docker-compose build
# Should complete without errors
```

### Test API Endpoint
```bash
curl -X POST http://localhost:9090/v1/models \
  -H "Authorization: Bearer test_key"
# Should return: {"models": ["af_bella", "af_sky"]}
```

### Test Audio Generation
```bash
curl -X POST http://localhost:9090/v1/audio/speech \
  -H "Authorization: Bearer test_key" \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello world", "voice": "af_bella"}' \
  --output test.wav
# Should create playable test.wav file
```

### Find Gradio on GamingPC
```bash
cd /path/to/openai-kokoro-tts
grep -r "import gradio" .
find . -name "*gradio*.py"
```

---

## RISK ASSESSMENT

| Issue | Severity | Probability | Impact |
|-------|----------|-------------|---------|
| Docker build fails | HIGH | 80% | Cannot deploy |
| Server crashes | HIGH | 95% | Service unusable |
| Gradio missing | HIGH | 50% | No demo UI |
| Voice errors | MEDIUM | 70% | Bad UX |

---

## 3-STEP IMMEDIATE ACTION PLAN

### STEP 1: Verify GamingPC (30 min)
- [ ] Confirm Gradio exists
- [ ] Test current GamingPC state
- [ ] Check for uncommitted changes
- [ ] Compare key files with GitHub

### STEP 2: Fix GitHub Bugs (2 hours)
- [ ] Delete duplicate onnx_tts_handler.py
- [ ] Fix server type mismatch bug
- [ ] Remove duplicate Dockerfile line
- [ ] Update README voice list
- [ ] Test Docker build
- [ ] Test API endpoints

### STEP 3: Sync from GamingPC (1 hour)
- [ ] Copy Gradio files
- [ ] Update pyproject.toml
- [ ] Run uv sync
- [ ] Test Gradio UI
- [ ] Push to GitHub
- [ ] Full integration test

**Total time**: 3.5 hours

---

## SUCCESS CHECKLIST

**Done when**:
- [ ] No critical bugs in GitHub
- [ ] Docker builds successfully
- [ ] API returns correct voice list (2 voices)
- [ ] Audio generation works
- [ ] Gradio UI present and functional
- [ ] GamingPC and GitHub match
- [ ] README accurate
- [ ] No duplicate code

---

## STALE STATUS CONFIRMED

**Latest commit**: 17a733b from 2025-03-21 (5+ months ago)

**Activity**: 
- Heavy development Jan 2025 (10 commits on Jan 16)
- One commit March 21
- No activity since (GitHub side)

**Conclusion**: Work moved to GamingPC, GitHub not updated

---

## ENVIRONMENT VARIABLE ISSUES

**Inconsistent paths**:

| File | Variable | Default |
|------|----------|---------|
| root handler | ONNX_MODEL_PATH | models/kokoro/kokoro-v0_19.onnx |
| package handler | ONNX_MODEL_PATH | models/kokoro/kokoro.onnx |
| convert script | Output | kokoro.onnx (no version) |

**Result**: File not found errors likely

**Fix**: Standardize on `kokoro.onnx` (matches conversion output)

---

## FILES INVENTORY SUMMARY

**Total**: 20+ files

**Working**: 11 files (utils, tests, configs, setup scripts)

**Broken**: 4 files (onnx handler bug, convert script, transformers mock, duplicate)

**Missing**: 1+ files (Gradio UI)

**Orphaned**: 2 files (root onnx handler, possibly cli_local_inference)

---

## CONTACTS FOR ESCALATION

**If blocked by**:
- Docker build failure → Check ONNX conversion, may need pre-converted files
- API crashes → Server bug #1, fix immediately
- Gradio not found → May need to build from scratch (see SYNC_ACTION_PLAN.md Appendix B)
- Audio quality issues → Check model version, may need different .pth

---

## NEXT REVIEW DATE

**When**: After GamingPC sync complete

**Focus**: 
- Verify fixes worked
- Test Gradio integration
- Performance benchmarks
- Security audit
- Plan next features (voice expansion, GPU support)

---

## DOCUMENT REFERENCES

- **Full analysis**: `SKEPTICAL_REVIEW.md`
- **Detailed plan**: `SYNC_ACTION_PLAN.md`
- **This summary**: `QUICK_REFERENCE.md`

---

**Last updated**: 2026-08-27  
**Review branch**: review/2026-08-27-skeptical  
**Status**: Analysis complete, awaiting GamingPC investigation
