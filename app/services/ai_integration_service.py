from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
from pydantic import BaseModel
import requests
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer
import os
import csv
import re
from langdetect import detect

from app.core.config import USE_GROQ, GROQ_MODEL, GROQ_API_KEY
from app.services.groq_translate import translate_one
from app.database.firestore_client import FirestoreClient

logger = logging.getLogger(__name__)

class AIProcessingResult(BaseModel):
    """Result of AI processing for a concern slip"""
    original_text: str
    processed_text: str
    detected_language: str
    translated: bool
    category: str
    urgency: str
    confidence_scores: Dict[str, float]
    processing_timestamp: datetime
    audit_trail: Dict[str, Any]

class AIIntegrationService:
    """
    Enhanced AI Integration Service for FacilityFix
    Handles translation, categorization, and audit trail management
    """
    
    def __init__(self):
        self.db = FirestoreClient()
        self.model_path = "app/models/facilityfix-ai"
        self._load_model_components()
        
    def _load_model_components(self):
        """Load AI model components and labels"""
        try:
            # Load categories and urgencies from CSV files
            self.categories = self._read_label_list(os.path.join(self.model_path, "categories.csv"))
            self.urgencies = self._read_label_list(os.path.join(self.model_path, "urgencies.csv"))
            
            self.categories_lower = [c.lower() for c in self.categories]
            self.urgencies_lower = [u.lower() for u in self.urgencies]
            
            self.num_cat = len(self.categories)
            self.num_urg = len(self.urgencies)
            
            logger.info(f"Loaded {self.num_cat} categories and {self.num_urg} urgency levels")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
            
            # Note: Model loading is handled in main.py for now
            # In production, consider moving model loading here for better encapsulation
            
        except Exception as e:
            logger.error(f"Failed to load AI model components: {str(e)}")
            raise
    
    def _read_label_list(self, path: str) -> List[str]:
        """Read labels from CSV file"""
        items = []
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                if not row:
                    continue
                val = row[0].strip()
                if not val or val.lower() == "0":
                    continue
                items.append(val)
        return items
    
    def _detect_language_taglish(self, text: str) -> str:
        """Enhanced language detection for Tagalog/English mix"""
        try:
            lang = detect(text)
        except Exception:
            lang = "en"
            
        if lang == "tl":
            return "tl"
            
        # Check for Tagalog keywords
        tagalog_keywords = {
            "ang", "ng", "sa", "si", "ni", "nasa", "wala", "meron", "yung", "dahil",
            "para", "kapag", "kahit", "itong", "baka", "kasi", "may", "tumutulo", 
            "kisame", "cr", "banyo", "gripo", "ilaw", "sira", "ayaw", "hindi"
        }
        
        tokens = re.findall(r"[A-Za-z]+", text.lower())
        tl_hits = sum(1 for t in tokens if t in tagalog_keywords)
        
        return "tl" if tl_hits >= 2 else "en"
    
    async def process_concern_description(
        self, 
        description: str, 
        concern_slip_id: str,
        force_translate: bool = False
    ) -> AIProcessingResult:
        """
        Complete AI processing pipeline for concern slip descriptions
        1. Language detection
        2. Translation (if needed)
        3. AI categorization and urgency detection
        4. Audit trail storage
        """
        processing_start = datetime.utcnow()
        
        try:
            # Step 1: Language Detection
            original_text = description.strip()
            detected_language = self._detect_language_taglish(original_text)
            
            # Step 2: Translation
            processed_text = original_text
            translated = False
            translation_error = None
            
            if USE_GROQ and (force_translate or detected_language == "tl"):
                try:
                    processed_text = translate_one(original_text) or original_text
                    translated = True
                    logger.info(f"Successfully translated text for concern {concern_slip_id}")
                except Exception as e:
                    logger.warning(f"Translation failed for concern {concern_slip_id}: {str(e)}")
                    translation_error = str(e)
                    processed_text = original_text
                    translated = False
            
            # Step 3: AI Categorization (using existing model from main.py)
            # For now, we'll make a request to the existing /predict endpoint
            category, urgency, confidence_scores = await self._get_ai_prediction(processed_text)
            
            # Step 4: Create audit trail
            audit_trail = {
                "concern_slip_id": concern_slip_id,
                "processing_timestamp": processing_start.isoformat(),
                "language_detection": {
                    "detected_language": detected_language,
                    "confidence": "high"  # langdetect doesn't provide confidence scores
                },
                "translation": {
                    "attempted": USE_GROQ and (force_translate or detected_language == "tl"),
                    "successful": translated,
                    "error": translation_error,
                    "original_length": len(original_text),
                    "translated_length": len(processed_text) if translated else None
                },
                "categorization": {
                    "category": category,
                    "urgency": urgency,
                    "confidence_scores": confidence_scores
                },
                "processing_duration_ms": (datetime.utcnow() - processing_start).total_seconds() * 1000
            }
            
            # Step 5: Store audit trail in Firestore
            await self._store_audit_trail(concern_slip_id, audit_trail)
            
            result = AIProcessingResult(
                original_text=original_text,
                processed_text=processed_text,
                detected_language=detected_language,
                translated=translated,
                category=category,
                urgency=urgency,
                confidence_scores=confidence_scores,
                processing_timestamp=processing_start,
                audit_trail=audit_trail
            )
            
            logger.info(f"AI processing completed for concern {concern_slip_id}: {category}/{urgency}")
            return result
            
        except Exception as e:
            logger.error(f"AI processing failed for concern {concern_slip_id}: {str(e)}")
            raise Exception(f"AI processing failed: {str(e)}")
    
    async def _get_ai_prediction(self, text: str) -> Tuple[str, str, Dict[str, float]]:
        """Get AI prediction using the existing model (placeholder for now)"""
        # This is a simplified version - in production, you'd integrate with your loaded model
        # For now, we'll use basic keyword matching as fallback
        
        text_lower = text.lower()
        
        # Simple keyword-based categorization as fallback
        if any(word in text_lower for word in ["leak", "water", "pipe", "faucet", "drain"]):
            category = "plumbing"
            urgency = "high" if "leak" in text_lower else "medium"
        elif any(word in text_lower for word in ["electrical", "power", "light", "outlet", "wire"]):
            category = "electrical"
            urgency = "high" if any(word in text_lower for word in ["spark", "shock", "fire"]) else "medium"
        elif any(word in text_lower for word in ["pest", "rat", "cockroach", "ant", "termite"]):
            category = "pest control"
            urgency = "high"  # Business rule: pest control is always high priority
        elif any(word in text_lower for word in ["ac", "aircon", "heating", "ventilation"]):
            category = "HVAC"
            urgency = "medium"
        elif any(word in text_lower for word in ["door", "window", "cabinet", "wood"]):
            category = "carpentry"
            urgency = "low"
        else:
            category = "masonry"
            urgency = "medium"
        
        # Mock confidence scores
        confidence_scores = {
            "category_confidence": 0.85,
            "urgency_confidence": 0.78,
            "overall_confidence": 0.81
        }
        
        return category, urgency, confidence_scores
    
    async def _store_audit_trail(self, concern_slip_id: str, audit_trail: Dict[str, Any]):
        """Store AI processing audit trail in Firestore"""
        try:
            audit_doc_id = f"{concern_slip_id}_ai_audit"
            success, _, error = await self.db.create_document(
                "ai_processing_audit", 
                audit_doc_id,
                audit_trail
            )
            
            if not success:
                logger.error(f"Failed to store audit trail for {concern_slip_id}: {error}")
            else:
                logger.info(f"Stored audit trail for concern {concern_slip_id}")
                
        except Exception as e:
            logger.error(f"Error storing audit trail: {str(e)}")
    
    async def get_processing_history(self, concern_slip_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve AI processing history for a concern slip"""
        try:
            audit_doc_id = f"{concern_slip_id}_ai_audit"
            success, audit_data, error = await self.db.get_document("ai_processing_audit", audit_doc_id)
            
            if success and audit_data:
                return audit_data
            else:
                logger.warning(f"No audit trail found for concern {concern_slip_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving processing history: {str(e)}")
            return None
    
    async def get_translation_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get translation usage statistics"""
        try:
            # Query audit trails from the last N days
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # This would require a more complex query in production
            # For now, return mock statistics
            return {
                "period_days": days,
                "total_processed": 150,
                "translations_attempted": 45,
                "translations_successful": 42,
                "translation_success_rate": 93.3,
                "languages_detected": {
                    "english": 105,
                    "tagalog": 45
                },
                "average_processing_time_ms": 1250,
                "most_common_categories": {
                    "plumbing": 35,
                    "electrical": 28,
                    "HVAC": 22,
                    "pest control": 18,
                    "carpentry": 15,
                    "masonry": 12
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting translation statistics: {str(e)}")
            raise Exception(f"Failed to get translation statistics: {str(e)}")
