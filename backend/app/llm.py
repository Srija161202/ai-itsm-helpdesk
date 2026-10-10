import logging
import re

from . import config

log = logging.getLogger("itsm.llm")
_tok = None
_model = None


def _load():
    global _tok, _model
    if _model is None:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        _tok = AutoTokenizer.from_pretrained(config.LLM_MODEL)
        _model = AutoModelForSeq2SeqLM.from_pretrained(config.LLM_MODEL)
        _model.eval()
    return _tok, _model


def _generate(prompt):
    import torch
    tok, model = _load()
    inputs = tok(prompt, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=200)
    return tok.decode(out[0], skip_special_tokens=True).strip()


def warmup():
    if config.USE_LLM:
        try:
            _load()
            log.info("LLM loaded: %s", config.LLM_MODEL)
        except Exception as exc:
            log.warning("LLM unavailable (%s) - extractive fallback will be used", exc)


def _clean(t):
    return re.sub(r"^#+\s*", "", t, flags=re.M).strip()


def extractive(hits):
    title = hits[0]["title"]
    return f"According to the knowledge article '{title}':\n\n" + "\n\n".join(_clean(h["text"]) for h in hits[:2])


def generate_answer(question, hits):
    if config.USE_LLM:
        try:
            ctx = "\n\n".join(_clean(h["text"]) for h in hits[:3])
            prompt = ("Answer the question using only the context below. If the context does not contain "
                      f"the answer, reply exactly: I don't know.\n\nContext:\n{ctx}\n\nQuestion: {question}\nAnswer:")
            out = _generate(prompt)
            if out and "i don't know" not in out.lower():
                return f"{out}\n\nSource article: {hits[0]['title']}", config.LLM_MODEL
        except Exception as exc:
            log.warning("LLM generation failed (%s) - using extractive answer", exc)
    return extractive(hits), "extractive-fallback"
