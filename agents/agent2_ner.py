"""
Agent 2 — Landmark / Free-text NER Agent (ML, selective)
==========================================================
Wraps shiprocket-ai/open-indicbert-indian-address-ner.

TRIGGER CONDITION (either):
  a) Agent 1's min confidence across {landmark, locality, building_name,
     sub_locality} is below the configured threshold (default 0.6), OR
  b) Agent 1's landmark/locality are None but the raw string contains landmark
     cue words (Near/Opp/Behind/Paas/Samne…), OR
  c) Agent 1 detected Devanagari / mixed-script content that may have been
     transliterated imperfectly.

MERGE POLICY:
  - Pincode / city / district / state ALWAYS come from Agent 1.
    Agent 2 may NEVER override these.
  - For free-text fields: use Agent 2's output only if its confidence is HIGHER
    than Agent 1's field confidence (or Agent 1 returned None).

Model notes confirmed from README:
  - Base: ai4bharat/indic-bert
  - Model size: ~396 MB
  - Labels: 23 (BIO scheme, see entity_mappings.json)
  - Key label: "landmarks" (not "landmark") — mapped to our "landmark" field
  - "house_details" ≈ building number/name context
  - Max context length: 128 tokens
  - Inference device: CUDA if available, else CPU
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from agents.agent1_parser import Agent1Result

logger = logging.getLogger(__name__)

MODEL_NAME = "shiprocket-ai/open-indicbert-indian-address-ner"

# Map model label names → our field names (confirmed from model card)
_LABEL_TO_FIELD: dict[str, str] = {
    "building_name": "building_name",
    "city":          "city",       # never overrides Agent 1
    "country":       None,         # not used in our schema
    "floor":         "floor",
    "house_details": "building_number",
    "landmarks":     "landmark",   # NOTE: "landmarks" not "landmark"
    "locality":      "locality",
    "pincode":       "pincode",    # never overrides Agent 1
    "road":          "road",
    "state":         "state",      # never overrides Agent 1
    "sub_locality":  "sub_locality",
}

# Fields Agent 1 always wins on — Agent 2 NEVER overwrites these
_AGENT1_WINS = frozenset(["pincode", "city", "district", "state"])


@dataclass
class Agent2Result:
    """Entity spans returned by IndicBERT NER, merged onto Agent1 base."""
    # Merged fields (Agent 1 fields + any Agent 2 improvements)
    building_number: Optional[str]
    building_name:   Optional[str]
    landmark:        Optional[str]
    locality:        Optional[str]
    sub_locality:    Optional[str]
    road:            Optional[str]
    floor:           Optional[str]
    # Per-field confidence after merge
    field_confidence: dict = field(default_factory=dict)
    # Raw entities from the model (for evidence trail)
    raw_entities: dict = field(default_factory=dict)
    # Was Agent 2 triggered?
    triggered: bool = False


class LandmarkNERAgent:
    """
    Agent 2: Selective IndicBERT NER for free-text address fields.

    The model is loaded lazily on first use (heavy import — ~396 MB download
    on first run). Subsequent calls reuse the cached model.
    """

    def __init__(self, confidence_threshold: float = 0.6):
        """
        Parameters
        ----------
        confidence_threshold:
            If Agent 1's min free-text field confidence is below this,
            Agent 2 is triggered. Default 0.6 as specified in the brief.
        """
        self.confidence_threshold = confidence_threshold
        self._model = None
        self._tokenizer = None
        self._device = None
        self._id2entity: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def should_run(self, agent1: Agent1Result) -> bool:
        """Decide whether to invoke the ML model for this request."""
        if agent1.has_devanagari:
            return True
        if agent1.freetext_min_confidence() < self.confidence_threshold:
            return True
        # landmark/locality are None but cue words present → parser missed them
        if agent1.has_landmark_cue and (
            agent1.landmark is None or agent1.locality is None
        ):
            return True
        return False

    def run(
        self,
        raw_address: str,
        agent1: Agent1Result,
        force: bool = False,
    ) -> tuple[Agent2Result, dict]:
        """
        Run the NER agent.

        Parameters
        ----------
        raw_address:  Original unmodified address string.
        agent1:       Result from Agent 1 (used for merge + trigger decision).
        force:        Override the trigger condition and always run.

        Returns
        -------
        (Agent2Result, trace_entry)
        """
        if not force and not self.should_run(agent1):
            # Return Agent 1's free-text fields unchanged
            result = Agent2Result(
                building_number  = agent1.building_number,
                building_name    = agent1.building_name,
                landmark         = agent1.landmark,
                locality         = agent1.locality,
                sub_locality     = agent1.sub_locality,
                road             = None,
                floor            = None,
                field_confidence = dict(agent1.field_confidence),
                raw_entities     = {},
                triggered        = False,
            )
            return result, self._trace(0.0, triggered=False)

        t0 = time.perf_counter()
        try:
            self._ensure_model_loaded()
        except Exception as exc:
            logger.error("Agent2: model load failed: %s", exc)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            # Degrade gracefully: pass through Agent 1 fields
            result = Agent2Result(
                building_number  = agent1.building_number,
                building_name    = agent1.building_name,
                landmark         = agent1.landmark,
                locality         = agent1.locality,
                sub_locality     = agent1.sub_locality,
                road             = None,
                floor            = None,
                field_confidence = dict(agent1.field_confidence),
                raw_entities     = {},
                triggered        = True,
            )
            return result, self._trace(elapsed_ms, triggered=True, error=str(exc))

        import torch  # noqa: F401 — already available after _ensure_model_loaded

        # -- Tokenize & predict -------------------------------------------
        inputs = self._tokenizer(
            raw_address,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=128,
        )
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)
            probs        = torch.nn.functional.softmax(outputs.logits, dim=-1)
            predicted_ids = torch.argmax(probs, dim=-1)
            conf_scores   = torch.max(probs, dim=-1)[0]

        tokens          = self._tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])
        predicted_labels = [self._id2entity.get(str(i.item()), "O") for i in predicted_ids[0]]
        confidences     = conf_scores[0].cpu().numpy()

        raw_entities = self._group_entities(tokens, predicted_labels, confidences)
        elapsed_ms   = (time.perf_counter() - t0) * 1000

        logger.info(
            "Agent2 NER completed in %.0fms - entities: %s",
            elapsed_ms, list(raw_entities.keys()),
        )

        # -- Merge with Agent 1 -------------------------------------------
        merged_fc = dict(agent1.field_confidence)
        merged = {
            "building_number": agent1.building_number,
            "building_name":   agent1.building_name,
            "landmark":        agent1.landmark,
            "locality":        agent1.locality,
            "sub_locality":    agent1.sub_locality,
            "road":            None,
            "floor":           None,
        }

        for model_label, entity_list in raw_entities.items():
            our_field = _LABEL_TO_FIELD.get(model_label)
            if our_field is None or our_field in _AGENT1_WINS:
                continue  # skip unmapped or locked fields

            # Pick best entity (highest confidence)
            best = max(entity_list, key=lambda e: e["confidence"])
            model_conf = float(best["confidence"])
            model_text = best["text"].strip()

            if not model_text:
                continue

            a1_conf = agent1.field_confidence.get(our_field, 0.0)
            # Use model output only if it's more confident than Agent 1
            if model_conf > a1_conf or merged.get(our_field) is None:
                merged[our_field]      = model_text
                merged_fc[our_field]   = model_conf

        result = Agent2Result(
            building_number  = merged["building_number"],
            building_name    = merged["building_name"],
            landmark         = merged["landmark"],
            locality         = merged["locality"],
            sub_locality     = merged["sub_locality"],
            road             = merged["road"],
            floor            = merged["floor"],
            field_confidence = merged_fc,
            raw_entities     = {k: [{"text": e["text"], "confidence": float(e["confidence"])} for e in v]
                                for k, v in raw_entities.items()},
            triggered        = True,
        )
        return result, self._trace(elapsed_ms, triggered=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_model_loaded(self) -> None:
        """Lazy-load the IndicBERT model + tokenizer on first use."""
        if self._model is not None:
            return

        logger.info("Agent2: loading IndicBERT model from HuggingFace Hub...")
        t0 = time.perf_counter()

        import torch
        from transformers import AutoTokenizer, AutoModelForTokenClassification

        self._device    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        self._model     = AutoModelForTokenClassification.from_pretrained(MODEL_NAME)
        self._model.to(self._device)
        self._model.eval()

        # Build id2entity from model config (confirmed from model card)
        self._id2entity = {
            "0":  "O",
            "1":  "B-building_name",
            "2":  "I-building_name",
            "3":  "B-city",
            "4":  "I-city",
            "5":  "B-country",
            "6":  "I-country",
            "7":  "B-floor",
            "8":  "I-floor",
            "9":  "B-house_details",
            "10": "I-house_details",
            "11": "B-locality",
            "12": "I-locality",
            "13": "B-pincode",
            "14": "I-pincode",
            "15": "B-road",
            "16": "I-road",
            "17": "B-state",
            "18": "I-state",
            "19": "B-sub_locality",
            "20": "I-sub_locality",
            "21": "B-landmarks",
            "22": "I-landmarks",
        }

        elapsed = (time.perf_counter() - t0) * 1000
        logger.info(
            "Agent2: model loaded in %.0fms on %s (size ~396MB)",
            elapsed, self._device,
        )

    @staticmethod
    def _group_entities(
        tokens: list[str],
        labels: list[str],
        confidences,  # numpy array
    ) -> dict[str, list[dict]]:
        """
        Convert BIO token/label/confidence triples into grouped entity dicts.

        IndicBERT uses ai4bharat/indic-bert which is a SentencePiece model:
          - ▁ (U+2581 LOWER ONE EIGHTH BLOCK) marks the START of a new word
          - Continuation pieces have NO ▁ prefix (join directly, no space)
          - Contrast with WordPiece where continuations use ## prefix

        So the join rule is:
          - If token starts with ▁  → strip ▁, prepend a space (new word)
          - Otherwise               → join directly (continuation piece)
        """
        SENT_PIECE_SPACE = "\u2581"  # ▁
        SKIP_TOKENS = {"[CLS]", "[SEP]", "[PAD]", "<pad>", "<s>", "</s>"}

        entities: dict[str, list[dict]] = {}
        current: dict | None = None

        for token, label, conf in zip(tokens, labels, confidences):
            if token in SKIP_TOKENS:
                continue

            if label.startswith("B-"):
                if current:
                    _flush(entities, current)
                entity_type = label[2:]
                # Strip the ▁ word-start marker from first token
                clean_token = token.lstrip(SENT_PIECE_SPACE)
                current = {"type": entity_type, "text": clean_token, "confidence": float(conf)}

            elif label.startswith("I-") and current:
                entity_type = label[2:]
                if entity_type == current["type"]:
                    if token.startswith(SENT_PIECE_SPACE):
                        # New word boundary inside the entity
                        current["text"] += " " + token.lstrip(SENT_PIECE_SPACE)
                    else:
                        # Continuation subword piece — join directly
                        current["text"] += token
                    current["confidence"] = (current["confidence"] + float(conf)) / 2

            elif label == "O":
                if current:
                    _flush(entities, current)
                    current = None

        if current:
            _flush(entities, current)

        # Final cleanup: strip any remaining ▁ or extra spaces
        for elist in entities.values():
            for e in elist:
                e["text"] = (
                    e["text"]
                    .replace(SENT_PIECE_SPACE, " ")
                    .replace("  ", " ")
                    .strip()
                )

        return entities

    @staticmethod
    def _trace(
        elapsed_ms: float,
        triggered: bool = True,
        error: str | None = None,
    ) -> dict:
        return {
            "agent": "Agent2_LandmarkNER",
            "latency_ms": round(elapsed_ms, 2),
            "approximate_cost_usd": 0.0,  # local model inference
            "ran": triggered,
            "error": error,
        }


def _flush(entities: dict, current: dict) -> None:
    """Append the current entity to the entities dict."""
    etype = current["type"]
    if etype not in entities:
        entities[etype] = []
    entities[etype].append({"text": current["text"], "confidence": current["confidence"]})


# --- Module-level singleton (shared across pipeline calls) ----------------
_ner_agent_instance: LandmarkNERAgent | None = None


def get_ner_agent(confidence_threshold: float = 0.6) -> LandmarkNERAgent:
    """Return the module-level singleton NER agent."""
    global _ner_agent_instance
    if _ner_agent_instance is None:
        _ner_agent_instance = LandmarkNERAgent(confidence_threshold=confidence_threshold)
    return _ner_agent_instance
