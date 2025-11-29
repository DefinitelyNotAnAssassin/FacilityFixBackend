from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import re
import csv

from pydantic import BaseModel
from langdetect import detect
from app.core.scheduler import start_scheduler, stop_scheduler

import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, RobertaConfig, RobertaModel, RobertaPreTrainedModel
import torch.nn as nn
from transformers.modeling_outputs import SequenceClassifierOutput

from app.core.config import USE_GROQ, GROQ_MODEL, GROQ_API_KEY
from app.core.config import settings, assert_groq_ready
from app.services.groq_translate import translate_one
from app.core.firebase_init import initialize_firebase, get_firebase_status
from app.services.firebase_storage_init import get_bucket_info, is_storage_available

# ---------- OPTIONAL ML/TRANSFORMERS IMPORTS (wrapped in try/except) ----------
# These imports will be attempted at startup. If you don't want models to load on import,
# move the heavy initialization into a startup event or another background task.
ml_available = True
try:
    from pydantic import BaseModel
    from langdetect import detect
    import torch
    from transformers import (
        AutoTokenizer, AutoModelForSeq2SeqLM,
        AutoModelForSequenceClassification, TextClassificationPipeline
    )
except Exception as e:
    ml_available = False
    ml_import_error = str(e)

# Initialize Firebase first
print("🔥 Initializing Firebase for FastAPI app...")
firebase_status = get_firebase_status()
print(f"Firebase status: {firebase_status}")

if not firebase_status['available']:
    success = initialize_firebase()
    if success:
        print("✅ Firebase initialized successfully")
    else:
        print("⚠️ Firebase initialization failed - app will run without Firebase features")

print("\n📦 Initializing Firebase Storage...")
storage_info = get_bucket_info()
if storage_info['available']:
    print(f"✅ Storage initialized: {storage_info['bucket_path']}")
else:
    print(f"⚠️ Storage initialization failed: {storage_info.get('error', 'Unknown error')}")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FacilityFix API",
    description="Smart Maintenance and Repair Analytics Management System",
    version="1.0.0"
)

origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:53054",         # if you test with that dev port
    "http://localhost:62855",         # if you test with that dev port
    "http://localhost:56355",         # if you test with that dev port

    "http://192.168.1.12:8080",       # if you open from other devices
    "http://192.168.1.8:8080",      
    "http://192.168.1.8:8000",      

]

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust as needed for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== AUTOMATIC ESCALATION SCHEDULER ====================
@app.on_event("startup")
async def startup_event():
    """Start automatic escalation scheduler on app startup"""
    logger.info("🚀 FastAPI startup event triggered")
    start_scheduler()

@app.on_event("shutdown")
async def shutdown_event():
    """Stop scheduler on app shutdown"""
    logger.info("⛔ FastAPI shutdown event triggered")
    stop_scheduler()

# ==================== END SCHEDULER ====================

def safe_include_router(router_module_path: str, router_name: str = "router"):
    """Safely include a router with error handling"""
    try:
        module = __import__(router_module_path, fromlist=[router_name])
        router = getattr(module, router_name)
        app.include_router(router)
        logger.info(f"✅ Successfully included {router_module_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to include {router_module_path}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# Include routers with error handling
logger.info("Loading routers...")

# Try to include each router individually
routers_to_load = [
    ("app.routers.auth", "Authentication"),
    ("app.routers.database", "Database"),
    ("app.routers.users", "Users"),
    ("app.routers.profiles", "Profiles"),
    ("app.routers.concern_slips", "Concern Slips"),
    ("app.routers.job_services", "Job Services"),
    ("app.routers.tenant_job_services", "Tenant Job Services"),
    ("app.routers.work_order_permits", "Work Order Permits"),
    ("app.routers.tenant_requests", "Tenant Requests"),
    ("app.routers.inventory", "Inventory Management"),
    ("app.routers.equipment", "Equipment Registry"),
    ("app.routers.maintenance_calendar", "Maintenance"),  # Update maintenance router to use /maintenance prefix instead of /maintenance-calendar
    ("app.routers.notifications", "Notifications"),
    ("app.routers.websocket", "WebSocket"),
    ("app.routers.announcements", "Announcements"),
    ("app.routers.file_storage", "File Storage"),
    ("app.routers.analytics", "Analytics"),
    ("app.routers.reporting", "Reporting & Analytics"),
    ("app.routers.admin_dashboard", "Admin Dashboard"), 
    ("app.routers.maintenance", "Maintenance"),
    ("app.routers.chat", "Chat"),
    ("app.routers.attachments", "Attachments"),
    # ("app.routers.attachments", "Attachments"), # Deprecated in favor of file_storage
]

successful_routers = []
failed_routers = []

for router_path, router_description in routers_to_load:
    if safe_include_router(router_path):
        successful_routers.append(router_description)
    else:
        failed_routers.append(router_description)

logger.info(f"Successfully loaded routers: {successful_routers}")
if failed_routers:
    logger.warning(f"Failed to load routers: {failed_routers}")

@app.get("/")
async def root():
    firebase_status = get_firebase_status()
    storage_info = get_bucket_info()
    return {
        "message": "Welcome to the FacilityFix API",
        "firebase_status": firebase_status,
        "storage_status": storage_info,
        "loaded_routers": successful_routers,
        "failed_routers": failed_routers
    }

@app.get("/health")
async def health_check():
    firebase_status = get_firebase_status()
    storage_info = get_bucket_info()
    return {
        "status": "healthy",
        "firebase_available": firebase_status['available'],
        "storage_available": storage_info['available'],
        "loaded_routers": len(successful_routers),
        "failed_routers": len(failed_routers)
    }

# ---------- OPTIONAL ML/TRANSFORMERS ENDPOINTS ----------
# ---------------- Health & quick translator ----------------
@app.get("/healthz")
def health():
    return {
        "use_groq": USE_GROQ,
        "groq_model": GROQ_MODEL,
        "groq_key_present": bool(GROQ_API_KEY),
        "groq_key_endswith": (GROQ_API_KEY[-4:] if GROQ_API_KEY else None),
    }


class _TIn(BaseModel):
    text: str


@app.post("/_translate_only")
def _translate_only(body: _TIn):
    out = translate_one(body.text)
    return {"in": body.text, "out": out}


# ---------------- Labels: load EXACT training order from CSV ----------------
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "facilityfix-ai")

def _read_label_list(path: str):
    if not os.path.exists(path):
        logger.error(f"Label file not found: {path}")
        return []
    
    items = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                if not row:
                    continue
                val = row[0].strip()
                # skip header/stray index lines like "0"
                if not val or val.lower() == "0":
                    continue
                items.append(val)
    except Exception as e:
        logger.error(f"Error reading label file {path}: {e}")
        return []
    return items

try:
    CATEGORIES = _read_label_list(os.path.join(MODEL_PATH, "categories.csv"))
    URGENCIES  = _read_label_list(os.path.join(MODEL_PATH, "urgencies.csv"))
    
    if not CATEGORIES:
        logger.warning("No categories loaded, using defaults")
        CATEGORIES = ["Electrical", "Plumbing", "HVAC", "Structural", "Pest Control", "Other"]
    
    if not URGENCIES:
        logger.warning("No urgencies loaded, using defaults")
        URGENCIES = ["Low", "Medium", "High"]
        
except Exception as e:
    logger.error(f"Error loading label files: {e}")
    # Fallback to default categories and urgencies
    CATEGORIES = ["Electrical", "Plumbing", "HVAC", "Masonry", "Pest Control", "Carpentry", "Other"]
    URGENCIES = ["Low", "Medium", "High"]

CATEGORIES_LOWER = [c.lower() for c in CATEGORIES]
URGENCIES_LOWER  = [u.lower() for u in URGENCIES]

NUM_CAT = len(CATEGORIES)   # 6
NUM_URG = len(URGENCIES)    # 3
NUM_LABELS = NUM_CAT + NUM_URG

print("[Labels] Categories:", CATEGORIES)
print("[Labels] Urgencies:", URGENCIES)


# ---------------- Tokenizer & Multi-head Model ----------------
tokenizer = None
try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
    logger.info("✅ Tokenizer loaded successfully")
except Exception as e:
    logger.error(f"❌ Failed to load tokenizer: {e}")

hf_config = RobertaConfig.from_pretrained(
    "roberta-base",
    num_labels=NUM_LABELS,
    problem_type="single_label_classification",
)

class MultiHeadRoberta(RobertaPreTrainedModel):
    """
    Matches your checkpoint keys:
      - cat_head.weight/bias  [6, 768], [6]
      - urg_head.weight/bias  [3, 768], [3]
    """
    def __init__(self, config, num_cat: int, num_urg: int):
        super().__init__(config)
        self.num_cat = num_cat
        self.num_urg = num_urg
        self.roberta = RobertaModel(config, add_pooling_layer=True)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)
        self.cat_head = nn.Linear(config.hidden_size, num_cat)
        self.urg_head = nn.Linear(config.hidden_size, num_urg)
        self.post_init()

    def forward(self, input_ids=None, attention_mask=None, token_type_ids=None, **kwargs):
        outputs = self.roberta(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
        )
        # ✅ Use MEAN pool instead of pooler_output/CLS
        rep = _mean_pool(outputs.last_hidden_state, attention_mask)  # [B, H]
        x = self.dropout(rep)
        cat_logits = self.cat_head(x)  # [B, num_cat]
        urg_logits = self.urg_head(x)  # [B, num_urg]
        logits = torch.cat([cat_logits, urg_logits], dim=-1)  # [B, num_cat+num_urg]
        return SequenceClassifierOutput(logits=logits)

def _mean_pool(last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    """Mean-pool token embeddings using the attention mask."""
    # last_hidden_state: [B, T, H], attention_mask: [B, T]
    mask = attention_mask.unsqueeze(-1).type_as(last_hidden_state)  # [B, T, 1]
    summed = (last_hidden_state * mask).sum(dim=1)                  # [B, H]
    counts = mask.sum(dim=1).clamp(min=1e-9)                        # [B, 1]
    return summed / counts

# Instantiate and manually load weights (remap enc.* → roberta.*)
model = MultiHeadRoberta(hf_config, num_cat=NUM_CAT, num_urg=NUM_URG)
model_loaded = False

def _remap_enc_to_roberta_keys(sd: dict) -> dict:
    """Remap Kaggle-saved 'enc.*' keys to HF's expected 'roberta.*' keys."""
    remapped = {}
    for k, v in sd.items():
        nk = k
        if k.startswith("enc."):
            nk = "roberta." + k[len("enc."):]  # enc.* → roberta.*
        # heads already match your class: cat_head.*, urg_head.*
        remapped[nk] = v
    return remapped

ckpt_path = os.path.join(MODEL_PATH, "pytorch_model.bin")

if os.path.exists(ckpt_path):
    try:
        state = torch.load(ckpt_path, map_location="cpu")
        state = _remap_enc_to_roberta_keys(state)
        missing, unexpected = model.load_state_dict(state, strict=False)
        print("[Checkpoint] missing keys:", missing)
        print("[Checkpoint] unexpected keys:", unexpected)
        model.eval()  # turn off dropout
        model_loaded = True
        logger.info("✅ Model loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to load model weights: {e}")
        model_loaded = False
else:
    logger.warning(f"❌ Model file not found: {ckpt_path}")
    logger.info("The model will use random weights. Please ensure pytorch_model.bin is in the correct location.")
    model_loaded = False

# ---------------- Helpers ----------------
TAGALOG_STOPWORDS = {
    "ang","ng","sa","si","ni","nasa","wala","meron","yung","dahil",
    "para","kapag","kahit","itong","baka","kasi","may","tumutulo","kisame","cr"
}

def _detect_lang_taglish(text: str) -> str:
    try:
        lang = detect(text)
    except Exception:
        lang = "en"
    if lang == "tl":
        return "tl"
    tokens = re.findall(r"[A-Za-z]+", text.lower())
    tl_hits = sum(1 for t in tokens if t in TAGALOG_STOPWORDS)
    return "tl" if tl_hits >= 2 else "en"


# ---------------- Request/Response models ----------------
class PredictIn(BaseModel):
    description: str


class PredictOut(BaseModel):
    original_text: str
    processed_text: str
    detected_language: str
    translated: bool
    category: str
    urgency: str


# ---------------- Prediction endpoint ----------------
@app.post("/predict", response_model=PredictOut)
def predict(inp: PredictIn, force_translate: bool = Query(False)):
    if not model_loaded or tokenizer is None:
        logger.error("Model or tokenizer not available")
        return PredictOut(
            original_text=inp.description,
            processed_text=inp.description,
            detected_language="en",
            translated=False,
            category="Other",
            urgency="Medium"
        )
    
    original = inp.description.strip()
    lang = _detect_lang_taglish(original)

    processed = original
    translated = False

    if USE_GROQ and (force_translate or lang == "tl"):
        try:
            processed = translate_one(original) or original
            translated = True
        except Exception as e:
            print(f"[Predict] Falling back to original (Groq failed): {e}")
            processed = original
            translated = False

    inputs = tokenizer(
        processed,
        return_tensors="pt",
        truncation=True,
        padding="max_length",
        max_length=256
    )
    with torch.no_grad():
        outputs = model(**inputs)

    logits = outputs.logits
    cat_logits = logits[:, :NUM_CAT]
    urg_logits = logits[:, NUM_CAT:]

    cat_id = int(cat_logits.argmax(dim=-1).item())
    urg_id = int(urg_logits.argmax(dim=-1).item())

    category = CATEGORIES[cat_id]
    category_l = CATEGORIES_LOWER[cat_id]
    urgency  = URGENCIES[urg_id]

    # Business rule (keep if required by prof): pest control is always HIGH
    if category_l == "pest control":
        urgency = "high"

    return PredictOut(
        original_text=original,
        processed_text=processed,
        detected_language=lang,
        translated=translated,
        category=category,
        urgency=urgency,
    )


# ---------------- Debug endpoint ----------------
class _DbgIn(BaseModel):
    text: str

@app.post("/_debug_logits")
def _debug_logits(body: _DbgIn, force_translate: bool = Query(False)):
    if not model_loaded or tokenizer is None:
        return {
            "error": "Model or tokenizer not available",
            "input_text": body.text,
            "processed_text": body.text,
            "detected_language": "en"
        }
    
    # detect + optional translate (same logic as /predict)
    text = body.text.strip()
    lang = _detect_lang_taglish(text)
    processed = text
    if USE_GROQ and (force_translate or lang == "tl"):
        try:
            processed = translate_one(text) or text
        except Exception as e:
            print(f"[_debug_logits] translate failed, using original: {e}")
            processed = text

    inputs = tokenizer(
        processed,
        return_tensors="pt",
        truncation=True,
        padding="max_length",
        max_length=256,
    )
    with torch.no_grad():
        outputs = model(**inputs)

    logits = outputs.logits
    cat_logits = logits[:, :NUM_CAT]
    urg_logits = logits[:, NUM_CAT:]

    cat_probs = F.softmax(cat_logits, dim=-1).squeeze(0).tolist()
    urg_probs = F.softmax(urg_logits, dim=-1).squeeze(0).tolist()

    cat_scores = sorted(
        [{"label": CATEGORIES[i], "score": float(cat_probs[i])} for i in range(NUM_CAT)],
        key=lambda x: x["score"], reverse=True
    )[:3]
    urg_scores = sorted(
        [{"label": URGENCIES[i], "score": float(urg_probs[i])} for i in range(NUM_URG)],
        key=lambda x: x["score"], reverse=True
    )

    return {
        "input_text": text,
        "processed_text": processed,
        "detected_language": lang,
        "categories_top3": cat_scores,
        "urgencies": urg_scores,
        "cat_argmax": cat_scores[0]["label"],
        "urg_argmax": urg_scores[0]["label"],
        "used_order": {"categories": CATEGORIES, "urgencies": URGENCIES},
    }
