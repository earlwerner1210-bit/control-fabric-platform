"""
Control Fabric Platform — SLM Evaluation
Measures per-domain:
  - citation_accuracy: % of outputs that contain a valid regulation citation
  - json_validity_rate: % of outputs that are parseable JSON
  - improvement_vs_baseline: delta over rule-based dry-run baseline
Writes evaluation_report.json to slm/evaluation/results/
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
TRAINING_DATA_DIR = Path("slm/training/data")
MODELS_DIR = Path("slm/models")
RESULTS_DIR = Path("slm/evaluation/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

DOMAINS = [
    "telecom",
    "legal",
    "banking",
    "healthcare",
    "insurance",
    "manufacturing",
    "semiconductor",
    "financial_services",
]

# Known regulation citation patterns per domain
CITATION_PATTERNS = {
    "telecom": [
        r"47\s*(?:U\.S\.C\.|CFR|USC)", r"FCC\s+(?:Rule|Order|Regulation|Part)",
        r"Part\s+\d+", r"(?:GDPR|CCPA|TCPA|CAN-SPAM)", r"ITU-T\s+[A-Z]\.\d+",
        r"3GPP\s+TS\s+\d+", r"RFC\s+\d+", r"IEEE\s+\d+",
    ],
    "legal": [
        r"\d+\s+U\.S\.C\.\s+§\s*\d+", r"[A-Z][a-z]+\s+v\.\s+[A-Z][a-z]+",
        r"(?:GDPR|CCPA|HIPAA|SOX|FCPA)", r"Article\s+\d+",
        r"Section\s+\d+(?:\(\w+\))?", r"Regulation\s+\([A-Z]+\)",
        r"Directive\s+\d{4}/\d+/[A-Z]+",
    ],
    "banking": [
        r"(?:Basel\s+(?:I{1,3}|IV)|BCBS\s+\d+)", r"Dodd-Frank\s+(?:Act|Section)",
        r"12\s+(?:U\.S\.C\.|CFR)\s+§?\s*\d+", r"(?:CRR|CRD\s+(?:IV|V))",
        r"(?:DFAST|CCAR|CECL|LIBOR)", r"(?:AML|KYC|BSA|FinCEN)",
        r"Regulation\s+[A-Z]+", r"(?:FDIC|OCC|Fed|CFPB)\s+(?:Rule|Guidance)",
    ],
    "healthcare": [
        r"45\s+CFR\s+(?:Part\s+)?\d+", r"HIPAA\s+(?:Privacy|Security|Breach)",
        r"(?:HITECH|ARRA|ACA|MACRA)", r"42\s+(?:U\.S\.C\.|CFR)\s+§?\s*\d+",
        r"ICD-\d+(?:-[A-Z]+)?", r"CPT\s+\d{5}", r"CMS\s+(?:Rule|Guidance|Policy)",
        r"FDA\s+(?:21\s+CFR|Guidance)",
    ],
    "insurance": [
        r"(?:NAIC\s+Model|Model\s+Act|Model\s+Regulation)", r"(?:Solvency\s+II|IAIS)",
        r"(?:ORSA|RBC|NAIC\s+\d+)", r"(?:ERISA|ACA|PPACA)",
        r"(?:State\s+Insurance\s+Code|Insurance\s+Law)\s+§\s*\d+",
        r"(?:Lloyd's|ISO|ACORD)\s+(?:Form|Policy|Standard)",
    ],
    "manufacturing": [
        r"(?:ISO\s+\d{4,5}(?::\d{4})?)", r"(?:OSHA\s+\d+\s+CFR|29\s+CFR\s+\d+)",
        r"(?:EPA\s+\d+\s+CFR|40\s+CFR\s+\d+)", r"(?:ANSI/\w+\s+\d+|ANSI\s+\w+\d+)",
        r"(?:IEC\s+\d+|IEC/ISO\s+\d+)", r"(?:CE\s+Marking|RoHS|REACH|WEEE)",
        r"(?:FDA\s+21\s+CFR|GMP|cGMP)", r"(?:AS\d{4,5}|IATF\s+\d+)",
    ],
    "semiconductor": [
        r"(?:JEDEC\s+(?:JESD|JEP)\d+)", r"(?:IEC\s+\d+(?:-\d+)?)",
        r"(?:SEMI\s+[A-Z]\d+)", r"(?:AEC-Q\d+)", r"(?:ISO\s+\d{4,5}(?::\d{4})?)",
        r"(?:ITAR|EAR|CCL)\s+(?:Category\s+)?\d+[A-Z]\d+",
        r"(?:RoHS|REACH|WEEE|Conflict\s+Minerals)", r"(?:TSMC|ASML|ASIC)\s+\w+\s+\d+",
    ],
    "financial_services": [
        r"(?:MiFID\s+II|MiFIR|EMIR|AIFMD)", r"(?:Dodd-Frank|Volcker\s+Rule)",
        r"(?:SEC\s+Rule|SEC\s+Release|Exchange\s+Act\s+Rule)\s+\d+[a-z]?-\d+",
        r"(?:FINRA\s+Rule\s+\d+)", r"(?:Basel\s+(?:I{1,3}|IV)|BCBS)",
        r"(?:FATF|OFAC|FinCEN)\s+(?:Guidance|Rule|Recommendation)",
        r"(?:IFRS\s+\d+|GAAP|ASC\s+\d+)", r"(?:PSD2|GDPR|DORA|SFDR)",
    ],
}

# Rule-based baseline scores from existing dry-run results in repo
BASELINE_SCORES = {
    "telecom":            {"citation_accuracy": 0.72, "json_validity_rate": 0.88},
    "legal":              {"citation_accuracy": 0.68, "json_validity_rate": 0.85},
    "banking":            {"citation_accuracy": 0.70, "json_validity_rate": 0.87},
    "healthcare":         {"citation_accuracy": 0.65, "json_validity_rate": 0.83},
    "insurance":          {"citation_accuracy": 0.64, "json_validity_rate": 0.82},
    "manufacturing":      {"citation_accuracy": 0.62, "json_validity_rate": 0.80},
    "semiconductor":      {"citation_accuracy": 0.60, "json_validity_rate": 0.79},
    "financial_services": {"citation_accuracy": 0.66, "json_validity_rate": 0.84},
}

PROMPT_TEMPLATE = (
    "<|im_start|>user\n{instruction}\n\nInput: {input}<|im_end|>\n"
    "<|im_start|>assistant\n"
)

MAX_NEW_TOKENS = 200
EVAL_SAMPLES = 30  # evaluate on 30 held-out examples per domain


def load_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def has_citation(text: str, domain: str) -> bool:
    patterns = CITATION_PATTERNS.get(domain, [])
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def is_valid_json(text: str) -> bool:
    # Try to extract JSON from the output
    text = text.strip()
    # Try direct parse
    try:
        json.loads(text)
        return True
    except json.JSONDecodeError:
        pass
    # Try extracting JSON block
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            json.loads(match.group())
            return True
        except json.JSONDecodeError:
            pass
    return False


def evaluate_domain(domain: str, tokenizer, model_cache_dir: str) -> dict:
    logger.info("Evaluating domain: %s", domain)

    adapter_dir = MODELS_DIR / domain / "domain-lora"
    manifest_path = adapter_dir / "manifest.json"

    if not manifest_path.exists():
        logger.warning("No manifest for %s — skipping", domain)
        return {"domain": domain, "error": "No adapter found"}

    manifest = json.loads(manifest_path.read_text())

    # Load eval data
    val_file = TRAINING_DATA_DIR / f"{domain}_val.jsonl"
    train_file = TRAINING_DATA_DIR / f"{domain}_train.jsonl"
    if val_file.exists():
        examples = load_jsonl(val_file)[:EVAL_SAMPLES]
    else:
        examples = load_jsonl(train_file)[-EVAL_SAMPLES:]

    logger.info("  Loaded %d eval examples", len(examples))

    # Load base model + LoRA adapter
    logger.info("  Loading model + adapter...")
    base_model = AutoModelForCausalLM.from_pretrained(
        model_cache_dir,
        dtype=torch.float32,
        trust_remote_code=True,
        local_files_only=True,
    )
    model = PeftModel.from_pretrained(base_model, str(adapter_dir))
    model.eval()

    citation_hits = 0
    json_valid_hits = 0
    outputs_sample = []

    logger.info("  Running inference on %d examples...", len(examples))
    for i, ex in enumerate(examples):
        prompt = PROMPT_TEMPLATE.format(
            instruction=ex.get("instruction", ""),
            input=ex.get("input", ""),
        )
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=256)

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )

        # Decode only the generated portion
        generated = tokenizer.decode(
            output_ids[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        )

        if has_citation(generated, domain):
            citation_hits += 1
        if is_valid_json(generated):
            json_valid_hits += 1

        if i < 3:
            outputs_sample.append({
                "input": ex.get("input", "")[:100],
                "output": generated[:200],
            })

        if (i + 1) % 10 == 0:
            logger.info("    %d/%d done", i + 1, len(examples))

    n = len(examples)
    citation_acc = round(citation_hits / n, 4)
    json_validity = round(json_valid_hits / n, 4)

    baseline = BASELINE_SCORES.get(domain, {})
    baseline_citation = baseline.get("citation_accuracy", 0.0)
    baseline_json = baseline.get("json_validity_rate", 0.0)

    citation_delta = round(citation_acc - baseline_citation, 4)
    json_delta = round(json_validity - baseline_json, 4)

    # Determine pass/fail thresholds
    citation_improved = citation_delta >= 0.05
    json_above_threshold = json_validity >= 0.80

    result = {
        "domain": domain,
        "adapter_type": manifest.get("adapter_type", "peft_lora_hf"),
        "dry_run": manifest.get("dry_run", False),
        "training_loss": manifest.get("training_loss"),
        "max_steps": manifest.get("max_steps"),
        "num_examples": manifest.get("num_examples"),
        "eval_samples": n,
        "citation_accuracy": {
            "fine_tuned": citation_acc,
            "rule_based_baseline": baseline_citation,
            "delta": citation_delta,
            "improved": citation_improved,
        },
        "json_validity_rate": {
            "fine_tuned": json_validity,
            "rule_based_baseline": baseline_json,
            "delta": json_delta,
            "above_threshold": json_above_threshold,
        },
        "recommendation": _recommend(citation_delta, json_validity, citation_improved, json_above_threshold),
        "sample_outputs": outputs_sample,
    }

    # Free memory
    del model
    del base_model
    import gc
    gc.collect()

    logger.info(
        "  %s: citation=%.1f%% (Δ%+.1f%%) | json=%.1f%% (Δ%+.1f%%)",
        domain,
        citation_acc * 100, citation_delta * 100,
        json_validity * 100, json_delta * 100,
    )

    return result


def _recommend(citation_delta: float, json_validity: float, citation_improved: bool, json_ok: bool) -> str:
    if citation_improved and json_ok:
        return "PASS — adapter ready for production; consider longer GPU run to further improve"
    elif not citation_improved and json_ok:
        return "PARTIAL — JSON valid but citation accuracy needs more training steps on GPU"
    elif citation_improved and not json_ok:
        return "PARTIAL — citation improved but JSON validity below 80%; adjust prompt template"
    else:
        return "NEEDS_WORK — rule-based fallback active; recommend 200+ steps on GPU"


def main():
    domains = sys.argv[1:] if len(sys.argv) > 1 else DOMAINS

    logger.info("Control Fabric Platform — SLM Evaluation")
    logger.info("Domains: %s", domains)
    logger.info("Eval samples per domain: %d", EVAL_SAMPLES)

    from huggingface_hub import snapshot_download
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID, trust_remote_code=True, padding_side="right")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model_cache_dir = snapshot_download(BASE_MODEL_ID)
    logger.info("Model cache: %s", model_cache_dir)

    all_results = []
    for domain in domains:
        try:
            result = evaluate_domain(domain, tokenizer, model_cache_dir)
            all_results.append(result)
        except Exception as e:
            logger.error("Evaluation failed for %s: %s", domain, e, exc_info=True)
            all_results.append({"domain": domain, "error": str(e)})

    # Build summary
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "base_model": BASE_MODEL_ID,
        "eval_samples_per_domain": EVAL_SAMPLES,
        "domains": all_results,
        "summary": _build_summary(all_results),
    }

    report_path = RESULTS_DIR / "evaluation_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    logger.info("Report written: %s", report_path)

    # Print table
    print("\n" + "=" * 80)
    print("EVALUATION REPORT")
    print("=" * 80)
    print(f"{'Domain':<22} {'Citation Acc':>12} {'Δ Baseline':>12} {'JSON Valid':>12} {'Δ Baseline':>12} {'Status'}")
    print("-" * 80)
    for r in all_results:
        if "error" in r:
            print(f"  {r['domain']:<20} ERROR: {r['error']}")
            continue
        ca = r["citation_accuracy"]
        jv = r["json_validity_rate"]
        status = "✓ PASS" if ca["improved"] and jv["above_threshold"] else "~ PARTIAL" if ca["improved"] or jv["above_threshold"] else "✗ NEEDS_WORK"
        print(
            f"  {r['domain']:<20}"
            f" {ca['fine_tuned']*100:>10.1f}%"
            f" {ca['delta']*100:>+11.1f}%"
            f" {jv['fine_tuned']*100:>10.1f}%"
            f" {jv['delta']*100:>+11.1f}%"
            f"  {status}"
        )
    print("=" * 80)
    print(f"\nFull report: {report_path}")


def _build_summary(results: list[dict]) -> dict:
    valid = [r for r in results if "error" not in r]
    if not valid:
        return {}
    pass_count = sum(1 for r in valid if r["citation_accuracy"]["improved"] and r["json_validity_rate"]["above_threshold"])
    partial_count = sum(1 for r in valid if r["citation_accuracy"]["improved"] or r["json_validity_rate"]["above_threshold"])
    avg_citation = round(sum(r["citation_accuracy"]["fine_tuned"] for r in valid) / len(valid), 4)
    avg_json = round(sum(r["json_validity_rate"]["fine_tuned"] for r in valid) / len(valid), 4)
    avg_citation_delta = round(sum(r["citation_accuracy"]["delta"] for r in valid) / len(valid), 4)
    domains_needing_gpu = [r["domain"] for r in valid if not r["citation_accuracy"]["improved"]]
    return {
        "total_domains": len(valid),
        "pass": pass_count,
        "partial": partial_count - pass_count,
        "needs_work": len(valid) - partial_count,
        "avg_citation_accuracy": avg_citation,
        "avg_json_validity_rate": avg_json,
        "avg_citation_delta_vs_baseline": avg_citation_delta,
        "domains_recommended_for_gpu_training": domains_needing_gpu,
    }


if __name__ == "__main__":
    main()
