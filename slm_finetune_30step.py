"""
Control Fabric Platform — PEFT LoRA Fine-Tuning (30-step, CPU-optimised)
Trains all 8 domain SLM adapters using HuggingFace PEFT + LoRA.
Config: 30 steps, batch_size=1, grad_accum=4 → 120 effective gradient updates.
Saves real LoRA adapter weights to slm/models/{domain}/domain-lora/
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/home/ubuntu/control-fabric-platform/slm_training.log"),
    ],
)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
BASE_MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
TRAINING_DATA_DIR = Path("slm/training/data")
MODELS_DIR = Path("slm/models")
RESULTS_DIR = Path("slm/evaluation/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

LORA_RANK = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
MAX_SEQ_LENGTH = 256
MAX_TRAIN_EXAMPLES = 120  # 30 steps × batch_size=1 × grad_accum=4
MAX_EVAL_EXAMPLES = 20
MAX_STEPS = 30
LEARNING_RATE = 2e-4
BATCH_SIZE = 1
GRAD_ACCUM = 4

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

CHAT_TEMPLATE = (
    "<|im_start|>user\n{instruction}\n\nInput: {input}<|im_end|>\n"
    "<|im_start|>assistant\n{output}<|im_end|>"
)


def load_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def format_example(ex: dict) -> str:
    return CHAT_TEMPLATE.format(
        instruction=ex.get("instruction", ""),
        input=ex.get("input", ""),
        output=ex.get("output", ""),
    )


def finetune_domain(domain: str, tokenizer, model_cache_dir: str) -> dict:
    logger.info("=" * 60)
    logger.info("Fine-tuning domain: %s  [%d steps]", domain, MAX_STEPS)
    logger.info("=" * 60)

    train_file = TRAINING_DATA_DIR / f"{domain}_train.jsonl"
    val_file = TRAINING_DATA_DIR / f"{domain}_val.jsonl"

    if not train_file.exists():
        logger.error("Training data not found: %s", train_file)
        return {"domain": domain, "success": False, "error": "No training data"}

    train_examples = load_jsonl(train_file)[:MAX_TRAIN_EXAMPLES]
    eval_examples = (
        load_jsonl(val_file)[:MAX_EVAL_EXAMPLES]
        if val_file.exists()
        else train_examples[-MAX_EVAL_EXAMPLES:]
    )
    logger.info("  Train: %d | Eval: %d", len(train_examples), len(eval_examples))

    # Format and tokenise
    train_texts = [format_example(ex) for ex in train_examples]
    eval_texts = [format_example(ex) for ex in eval_examples]

    def tokenise(texts: list[str]) -> dict:
        return tokenizer(
            texts,
            truncation=True,
            max_length=MAX_SEQ_LENGTH,
            padding="max_length",
            return_tensors="pt",
        )

    logger.info("  Tokenising...")
    train_enc = tokenise(train_texts)
    eval_enc = tokenise(eval_texts)

    train_dataset = Dataset.from_dict(
        {
            "input_ids": train_enc["input_ids"],
            "attention_mask": train_enc["attention_mask"],
            "labels": train_enc["input_ids"].clone(),
        }
    )
    eval_dataset = Dataset.from_dict(
        {
            "input_ids": eval_enc["input_ids"],
            "attention_mask": eval_enc["attention_mask"],
            "labels": eval_enc["input_ids"].clone(),
        }
    )

    # Load base model from local cache (already downloaded)
    logger.info("  Loading base model from cache: %s", model_cache_dir)
    model = AutoModelForCausalLM.from_pretrained(
        model_cache_dir,
        dtype=torch.float32,
        trust_remote_code=True,
        local_files_only=True,
    )

    # Apply LoRA
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        lora_dropout=LORA_DROPOUT,
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    trainable, total = model.get_nb_trainable_parameters()
    logger.info(
        "  Trainable params: %s / %s (%.4f%%)",
        f"{trainable:,}",
        f"{total:,}",
        100 * trainable / total,
    )

    # Output path
    adapter_dir = MODELS_DIR / domain / "domain-lora"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = adapter_dir / "checkpoints"
    checkpoint_dir.mkdir(exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(checkpoint_dir),
        max_steps=MAX_STEPS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        warmup_steps=5,
        learning_rate=LEARNING_RATE,
        fp16=False,
        bf16=False,
        logging_steps=10,
        eval_steps=30,
        save_steps=30,
        eval_strategy="steps",
        save_strategy="steps",
        load_best_model_at_end=False,
        report_to="none",
        dataloader_pin_memory=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )

    logger.info("  Training for %d steps...", MAX_STEPS)
    start = time.time()
    train_result = trainer.train()
    elapsed = round(time.time() - start, 1)

    train_loss = round(train_result.training_loss, 4)
    logger.info("  Done: %.1fs | loss=%.4f", elapsed, train_loss)

    # Save LoRA adapter weights
    model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))
    logger.info("  Adapter saved: %s", adapter_dir)

    # Write manifest — dry_run=False marks this as real trained weights
    manifest = {
        "domain": domain,
        "base_model": BASE_MODEL_ID,
        "lora_rank": LORA_RANK,
        "lora_alpha": LORA_ALPHA,
        "num_examples": len(train_dataset),
        "max_steps": MAX_STEPS,
        "training_loss": train_loss,
        "training_time_seconds": elapsed,
        "dry_run": False,
        "adapter_type": "peft_lora_hf",
        "created_at": datetime.now(UTC).isoformat(),
    }
    (adapter_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    logger.info("  Manifest written: dry_run=False, loss=%.4f", train_loss)

    # Free model memory before next domain
    del model
    del trainer
    import gc

    gc.collect()

    return {
        "domain": domain,
        "success": True,
        "training_loss": train_loss,
        "training_seconds": elapsed,
        "num_examples": len(train_dataset),
        "adapter_path": str(adapter_dir),
    }


def main():
    domains = sys.argv[1:] if len(sys.argv) > 1 else DOMAINS

    logger.info("Control Fabric Platform — PEFT LoRA Fine-Tuning (30-step)")
    logger.info("Base model: %s", BASE_MODEL_ID)
    logger.info("Domains: %s", domains)
    logger.info(
        "Steps per domain: %d | Batch: %d | GradAccum: %d", MAX_STEPS, BATCH_SIZE, GRAD_ACCUM
    )
    logger.info("CUDA: %s", torch.cuda.is_available())

    # Download / locate model cache
    logger.info("Resolving model cache for %s ...", BASE_MODEL_ID)
    from transformers import AutoTokenizer as AT

    tokenizer = AT.from_pretrained(BASE_MODEL_ID, trust_remote_code=True, padding_side="right")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Find the local cache path so we can load offline for each domain
    from huggingface_hub import snapshot_download

    model_cache_dir = snapshot_download(BASE_MODEL_ID)
    logger.info("Model cache: %s", model_cache_dir)

    all_results = []
    for domain in domains:
        try:
            result = finetune_domain(domain, tokenizer, model_cache_dir)
            all_results.append(result)
            logger.info(
                "COMPLETED %s: loss=%.4f time=%.1fs",
                domain,
                result["training_loss"],
                result["training_seconds"],
            )
        except Exception as e:
            logger.error("Domain %s FAILED: %s", domain, e, exc_info=True)
            all_results.append({"domain": domain, "success": False, "error": str(e)})

    # Print summary
    print("\n" + "=" * 60)
    print("ALL TRAINING COMPLETE")
    print("=" * 60)
    for r in all_results:
        if r.get("success"):
            print(
                f"  {r['domain']:<22} loss={r['training_loss']:.4f}"
                f"  time={r['training_seconds']}s"
                f"  examples={r['num_examples']}"
            )
        else:
            print(f"  {r['domain']:<22} FAILED: {r.get('error', 'unknown')}")

    # Save training summary
    summary_path = RESULTS_DIR / "training_summary.json"
    summary_path.write_text(json.dumps(all_results, indent=2))
    print(f"\nSummary: {summary_path}")


if __name__ == "__main__":
    main()
