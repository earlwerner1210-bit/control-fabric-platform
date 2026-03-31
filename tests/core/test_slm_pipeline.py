"""Tests for SLM training pipeline — corpus, scenarios, finetune, evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from slm.corpus.scraper import CorpusDocument, RegulatoryCorpusScraper
from slm.evaluation.evaluator import EvalMetrics, SLMEvaluator
from slm.training.finetune import FinetuneResult, LoRAConfig, MLXLoRAFineTuner
from slm.training.scenario_generator import SyntheticScenarioGenerator, TrainingExample


class TestCorpusScraper:
    def test_static_scrape_telecom(self, tmp_path: Path) -> None:
        scraper = RegulatoryCorpusScraper(
            domain="telecom",
            output_dir=str(tmp_path / "corpus"),
            mode="static",
        )
        docs = scraper.scrape()
        assert len(docs) > 0
        assert all(isinstance(d, CorpusDocument) for d in docs)
        assert all(d.domain == "telecom" for d in docs)

    def test_static_scrape_finserv(self, tmp_path: Path) -> None:
        scraper = RegulatoryCorpusScraper(
            domain="financial_services",
            output_dir=str(tmp_path / "corpus"),
            mode="static",
        )
        docs = scraper.scrape()
        assert len(docs) > 0
        assert any("FCA" in d.title or "DORA" in d.title or "PRA" in d.title for d in docs)

    def test_corpus_saves_json(self, tmp_path: Path) -> None:
        scraper = RegulatoryCorpusScraper(
            domain="telecom",
            output_dir=str(tmp_path / "corpus"),
        )
        scraper.scrape()
        corpus_file = tmp_path / "corpus" / "telecom_corpus.json"
        assert corpus_file.exists()
        data = json.loads(corpus_file.read_text())
        assert len(data) > 0
        assert "doc_id" in data[0]

    def test_corpus_document_to_dict(self) -> None:
        doc = CorpusDocument(
            doc_id="test-1",
            title="Test Doc",
            source="test",
            domain="telecom",
            text="Test text",
        )
        d = doc.to_dict()
        assert d["doc_id"] == "test-1"
        assert d["title"] == "Test Doc"

    def test_training_texts(self, tmp_path: Path) -> None:
        scraper = RegulatoryCorpusScraper(
            domain="telecom",
            output_dir=str(tmp_path / "corpus"),
        )
        scraper.scrape()
        texts = scraper.get_training_texts()
        assert len(texts) > 0
        assert all(isinstance(t, str) for t in texts)


class TestScenarioGenerator:
    def test_generate_telecom_scenarios(self, tmp_path: Path) -> None:
        gen = SyntheticScenarioGenerator(
            domain="telecom",
            output_dir=str(tmp_path / "data"),
            target_count=100,
        )
        examples = gen.generate()
        assert len(examples) == 100
        assert all(isinstance(e, TrainingExample) for e in examples)

    def test_generate_finserv_scenarios(self, tmp_path: Path) -> None:
        gen = SyntheticScenarioGenerator(
            domain="financial_services",
            output_dir=str(tmp_path / "data"),
            target_count=50,
        )
        examples = gen.generate()
        assert len(examples) == 50

    def test_scenario_distribution(self, tmp_path: Path) -> None:
        gen = SyntheticScenarioGenerator(
            domain="telecom",
            output_dir=str(tmp_path / "data"),
            target_count=300,
        )
        gen.generate()
        dist = gen.get_scenario_distribution()
        assert len(dist) > 0
        assert sum(dist.values()) == 300

    def test_creates_train_val_test_splits(self, tmp_path: Path) -> None:
        gen = SyntheticScenarioGenerator(
            domain="telecom",
            output_dir=str(tmp_path / "data"),
            target_count=100,
        )
        gen.generate()
        assert (tmp_path / "data" / "telecom_train.jsonl").exists()
        assert (tmp_path / "data" / "telecom_val.jsonl").exists()
        assert (tmp_path / "data" / "telecom_test.jsonl").exists()

    def test_training_example_to_dict(self) -> None:
        ex = TrainingExample(
            instruction="Test",
            input_text="Input",
            output_text="Output",
            domain="telecom",
            scenario_type="network_change",
        )
        d = ex.to_dict()
        assert d["instruction"] == "Test"
        assert d["domain"] == "telecom"

    def test_corpus_integration(self, tmp_path: Path) -> None:
        gen = SyntheticScenarioGenerator(
            domain="telecom",
            output_dir=str(tmp_path / "data"),
            corpus_texts=["NIS2 Article 21 requires incident handling."],
            target_count=50,
            seed=1,
        )
        examples = gen.generate()
        assert len(examples) == 50


class TestFineTuner:
    def test_dry_run(self, tmp_path: Path) -> None:
        config = LoRAConfig(output_dir=str(tmp_path / "models"))
        tuner = MLXLoRAFineTuner(config=config, domain="telecom")
        result = tuner.train(dry_run=True)
        assert result.success is True
        assert result.dry_run is True
        assert isinstance(result, FinetuneResult)

    def test_config_defaults(self) -> None:
        config = LoRAConfig()
        assert config.lora_rank == 16
        assert config.num_epochs == 3
        assert config.batch_size == 4

    def test_result_to_dict(self) -> None:
        result = FinetuneResult(success=True, dry_run=True)
        d = result.to_dict()
        assert d["success"] is True
        assert d["dry_run"] is True

    def test_dry_run_creates_manifest(self, tmp_path: Path) -> None:
        config = LoRAConfig(output_dir=str(tmp_path / "models"))
        tuner = MLXLoRAFineTuner(config=config, domain="telecom")
        result = tuner.train(dry_run=True)
        manifest_path = Path(result.adapter_path) / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert manifest["domain"] == "telecom"
        assert manifest["dry_run"] is True


class TestModelLoader:
    def test_singleton(self) -> None:
        from app.core.inference.domain_adapters.model_loader import DomainModelLoader

        DomainModelLoader.reset()
        loader1 = DomainModelLoader.instance()
        loader2 = DomainModelLoader.instance()
        assert loader1 is loader2
        DomainModelLoader.reset()

    def test_load_nonexistent_domain(self) -> None:
        from app.core.inference.domain_adapters.model_loader import DomainModelLoader

        DomainModelLoader.reset()
        loader = DomainModelLoader.instance()
        model = loader.load("nonexistent_domain_xyz")
        assert model.is_loaded is False
        assert model.domain == "nonexistent_domain_xyz"
        DomainModelLoader.reset()

    def test_list_models_empty(self) -> None:
        from app.core.inference.domain_adapters.model_loader import DomainModelLoader

        DomainModelLoader.reset()
        loader = DomainModelLoader.instance()
        models = loader.list_models()
        assert models == []
        DomainModelLoader.reset()

    def test_is_available_false(self) -> None:
        from app.core.inference.domain_adapters.model_loader import DomainModelLoader

        DomainModelLoader.reset()
        loader = DomainModelLoader.instance()
        assert loader.is_available("nonexistent_xyz") is False
        DomainModelLoader.reset()


class TestEvaluator:
    def test_eval_metrics_score(self) -> None:
        metrics = EvalMetrics(
            citation_accuracy=0.9,
            evidence_completeness=0.85,
            risk_accuracy=0.8,
            remediation_specificity=0.75,
            hallucination_rate=0.1,
            avg_latency_ms=5.0,
        )
        score = metrics.overall_score()
        assert 0 < score <= 100
        assert metrics.grade() in ["A", "B", "C", "D", "F"]

    def test_eval_metrics_grade_a(self) -> None:
        metrics = EvalMetrics(
            citation_accuracy=1.0,
            evidence_completeness=1.0,
            risk_accuracy=1.0,
            remediation_specificity=1.0,
            hallucination_rate=0.0,
            avg_latency_ms=1.0,
        )
        assert metrics.grade() == "A"

    def test_eval_metrics_to_dict(self) -> None:
        metrics = EvalMetrics(model_id="test", domain="telecom")
        d = metrics.to_dict()
        assert "overall_score" in d
        assert "grade" in d
        assert d["model_id"] == "test"

    def test_evaluator_no_test_data(self, tmp_path: Path) -> None:
        evaluator = SLMEvaluator(
            domain="telecom",
            test_data_path=str(tmp_path / "nonexistent.jsonl"),
            results_dir=str(tmp_path / "results"),
        )
        metrics = evaluator.evaluate(model_id="test")
        assert metrics.num_examples == 0

    def test_evaluator_with_test_data(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.jsonl"
        examples = [
            {
                "instruction": "Assess risk",
                "input": "Network change CR-1234",
                "output": "Risk assessment: HIGH\nNIS2 Article 21",
                "scenario_type": "network_change",
                "regulatory_refs": ["NIS2"],
            }
            for _ in range(5)
        ]
        with open(test_file, "w") as f:
            for ex in examples:
                f.write(json.dumps(ex) + "\n")

        evaluator = SLMEvaluator(
            domain="telecom",
            test_data_path=str(test_file),
            results_dir=str(tmp_path / "results"),
        )
        metrics = evaluator.evaluate(model_id="test")
        assert metrics.num_examples == 5
        assert metrics.overall_score() > 0

    def test_comparison(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.jsonl"
        examples = [
            {
                "instruction": "Classify incident",
                "input": "Security incident SI-5678",
                "output": "NIS2 Classification: HIGH",
                "scenario_type": "security_incident",
                "regulatory_refs": ["NIS2"],
            }
        ]
        with open(test_file, "w") as f:
            for ex in examples:
                f.write(json.dumps(ex) + "\n")

        evaluator = SLMEvaluator(
            domain="telecom",
            test_data_path=str(test_file),
            results_dir=str(tmp_path / "results"),
        )
        comparison = evaluator.compare()
        assert comparison.recommendation != ""
        assert "base" in comparison.to_dict()
        assert "finetuned" in comparison.to_dict()
