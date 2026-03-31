"""
SLM Training Pipeline CLI

End-to-end pipeline: scrape → generate → train → evaluate

Usage:
    python slm/run_pipeline.py --domain telecom --dry-run
    python slm/run_pipeline.py --domain telecom --live
    python slm/run_pipeline.py --status
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slm.corpus.scraper import RegulatoryCorpusScraper
from slm.evaluation.evaluator import SLMEvaluator
from slm.training.finetune import MLXLoRAFineTuner
from slm.training.scenario_generator import SyntheticScenarioGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_pipeline(domain: str, dry_run: bool = True, target_examples: int = 10000) -> dict:
    """Run the full SLM training pipeline."""
    logger.info("=" * 60)
    logger.info("SLM Training Pipeline — domain: %s, dry_run: %s", domain, dry_run)
    logger.info("=" * 60)

    results: dict = {
        "domain": domain,
        "dry_run": dry_run,
        "started_at": datetime.now(UTC).isoformat(),
        "stages": {},
    }

    # Stage 1: Corpus scraping
    logger.info("\n[1/4] Scraping regulatory corpus...")
    scraper = RegulatoryCorpusScraper(
        domain=domain,
        mode="static" if dry_run else "live",
    )
    documents = scraper.scrape()
    results["stages"]["corpus"] = {
        "documents": len(documents),
        "status": "complete",
    }
    logger.info("Corpus: %d documents", len(documents))

    # Stage 2: Scenario generation
    logger.info("\n[2/4] Generating synthetic training scenarios...")
    generator = SyntheticScenarioGenerator(
        domain=domain,
        corpus_texts=scraper.get_training_texts(),
        target_count=target_examples,
    )
    examples = generator.generate()
    distribution = generator.get_scenario_distribution()
    results["stages"]["generation"] = {
        "examples": len(examples),
        "distribution": distribution,
        "status": "complete",
    }
    logger.info("Generated: %d examples across %d scenarios", len(examples), len(distribution))

    # Stage 3: Fine-tuning
    logger.info("\n[3/4] Fine-tuning with LoRA...")
    finetuner = MLXLoRAFineTuner(domain=domain)
    ft_result = finetuner.train(dry_run=dry_run)
    results["stages"]["finetune"] = ft_result.to_dict()
    logger.info(
        "Fine-tune: success=%s, dry_run=%s, examples=%d",
        ft_result.success,
        ft_result.dry_run,
        ft_result.num_examples,
    )

    # Stage 4: Evaluation
    logger.info("\n[4/4] Evaluating model...")
    evaluator = SLMEvaluator(domain=domain)
    metrics = evaluator.evaluate(model_id="finetuned" if not dry_run else "dry-run")
    results["stages"]["evaluation"] = metrics.to_dict()
    logger.info(
        "Evaluation: score=%.1f, grade=%s, examples=%d",
        metrics.overall_score(),
        metrics.grade(),
        metrics.num_examples,
    )

    results["completed_at"] = datetime.now(UTC).isoformat()
    results["status"] = "complete"

    # Save pipeline results
    results_file = Path(f"slm/evaluation/results/{domain}_pipeline_results.json")
    results_file.write_text(json.dumps(results, indent=2))
    logger.info("\nPipeline complete. Results: %s", results_file)

    return results


def show_status() -> None:
    """Show status of all domain pipelines."""
    results_dir = Path("slm/evaluation/results")
    if not results_dir.exists():
        print("No pipeline results found.")
        return

    print(f"\n{'Domain':<20} {'Status':<12} {'Examples':<10} {'Score':<8} {'Grade'}")
    print("─" * 65)

    for result_file in sorted(results_dir.glob("*_pipeline_results.json")):
        data = json.loads(result_file.read_text())
        domain = data.get("domain", "unknown")
        status = data.get("status", "unknown")
        examples = data.get("stages", {}).get("generation", {}).get("examples", 0)
        eval_data = data.get("stages", {}).get("evaluation", {})
        score = eval_data.get("overall_score", 0)
        grade = eval_data.get("grade", "?")
        print(f"  {domain:<18} {status:<12} {examples:<10} {score:<8.1f} {grade}")

    models_dir = Path("slm/models")
    if models_dir.exists():
        print(f"\n{'Model Adapters':}")
        for adapter_dir in sorted(models_dir.iterdir()):
            if adapter_dir.is_dir():
                manifest = adapter_dir / "domain-lora" / "manifest.json"
                if manifest.exists():
                    m = json.loads(manifest.read_text())
                    print(
                        f"  {adapter_dir.name}: base={m.get('base_model', '?')}"
                        f" rank={m.get('lora_rank', '?')}"
                        f" dry_run={m.get('dry_run', '?')}"
                    )


def main() -> None:
    parser = argparse.ArgumentParser(description="SLM Training Pipeline")
    parser.add_argument("--domain", default="telecom", help="Domain to train")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run mode")
    parser.add_argument("--live", action="store_true", help="Live mode (attempt EUR-Lex fetch)")
    parser.add_argument("--examples", type=int, default=10000, help="Target training examples")
    parser.add_argument("--status", action="store_true", help="Show pipeline status")

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    dry_run = not args.live
    run_pipeline(domain=args.domain, dry_run=dry_run, target_examples=args.examples)


if __name__ == "__main__":
    main()
