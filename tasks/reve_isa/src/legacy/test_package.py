"""Controlled CPU contract tests. Inputs here are never research observations."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
import math
import posixpath
from pathlib import Path, PurePosixPath
import sys
import unittest
from unittest.mock import patch

import numpy as np
import torch
import yaml

from artifact_io import fingerprint, read_json, sha256_file
from broker_contract import build_request, check_receipt, validate_request
from evaluation_contract import EpochSelection, paired_bootstrap, sample_metrics, select_method, training_statistics
from official_model import checked_positions, enable_checkpointing, load_exact_state, pin_sdpa_attention, prepare_input
from posttrain import learning_rate_multiplier, validate_parameters
from release_io import check_metadata_table, checked_trial_indices
from source_parallel import separate_source_losses
from isa_loss import flatten_normalize, paired_info_nce

ROOT = Path(__file__).resolve().parent


class OfficialModelTests(unittest.TestCase):
    def tiny(self):
        from vendor.reve.configuration_reve import ReveConfig
        from vendor.reve.modeling_reve import Reve
        model = Reve(ReveConfig(embed_dim=8,depth=2,heads=2,head_dim=4,mlp_dim_ratio=2,
                                freqs=2,patch_size=4,patch_overlap=0))
        pin_sdpa_attention(model)
        return model

    def test_tiny_official_forward_and_checkpoint_gradient_equivalence(self):
        torch.manual_seed(3)
        plain = self.tiny()
        checkpointed = self.tiny()
        checkpointed.load_state_dict(plain.state_dict())
        enable_checkpointing(checkpointed)
        plain.train(); checkpointed.train()
        x = torch.randn(2,2,12)
        pos = torch.rand(2,2,3)
        actual = plain(x,pos)
        result = checkpointed(x,pos)
        self.assertEqual(tuple(actual.shape),(2,2,3,8))
        torch.testing.assert_close(actual,result,rtol=1e-6,atol=1e-6)
        actual.square().mean().backward(); result.square().mean().backward()
        for (name,a),(other,b) in zip(plain.named_parameters(),checkpointed.named_parameters(),strict=True):
            self.assertEqual(name,other)
            if name == "cls_query_token":
                self.assertIsNone(a.grad); self.assertIsNone(b.grad)
            else:
                self.assertTrue(torch.isfinite(a.grad).all())
                torch.testing.assert_close(a.grad,b.grad,rtol=1e-5,atol=1e-6)

    def test_strict_state_rejects_missing_extra_shape_nonfinite(self):
        module = torch.nn.Linear(3,2)
        state = {k:v.clone() for k,v in module.state_dict().items()}
        load_exact_state(module,state)
        for bad in (dict(weight=state["weight"]),dict(state,extra=torch.ones(1)),
                    dict(state,weight=torch.ones(2,4)),dict(state,weight=torch.full((2,3),float("nan")))):
            with self.assertRaises(ValueError):load_exact_state(module,bad)

    def test_position_bank_preserves_every_ordered_channel_and_rejects_unknown(self):
        class Bank:
            embedding=torch.arange(180,dtype=torch.float32).reshape(60,3)
            mapping={f"e{i}":i for i in range(60)}
        channels=[f"e{i}" for i in range(60)]
        torch.testing.assert_close(checked_positions(Bank(),channels),Bank.embedding)
        torch.testing.assert_close(checked_positions(Bank(),channels[::-1]),Bank.embedding.flip(0))
        for bad in (channels[:-1],channels[:-1]+[channels[0]],channels[:-1]+["missing"]):
            with self.assertRaises(ValueError):checked_positions(Bank(),bad)

    def test_raw_noclip_input_and_bf16_loss_precision(self):
        signals=torch.ones(2,60,2000)*125
        torch.testing.assert_close(prepare_input(signals),signals)
        with self.assertRaises(ValueError):prepare_input(signals[:,:,:1999])
        with self.assertRaises(ValueError):prepare_input(torch.full_like(signals,float("nan")))
        tokens=torch.randn(8,2,3,4).to(torch.bfloat16).requires_grad_(True)
        features=flatten_normalize(tokens)
        self.assertEqual(features.dtype,torch.float32)
        loss=paired_info_nce(features,temperature=0.1)[0]
        loss.backward()
        self.assertTrue(torch.isfinite(tokens.grad).all())


class MetadataPackageTests(unittest.TestCase):
    def table(self):
        channels=json.dumps([f"e{i}" for i in range(60)])
        return {"sample_id":[f"s{i}" for i in range(12)],"subject_id":["a"]*6+["b"]*6,
                "label_id":[0,1]*6,"channel_names_json":[channels]*12,"global_idx":list(range(12)),
                "session_id":["20130101","20130101","20130202","20130202","20130303","20130303"]*2,
                "trial_id":["1","2"]*6,"sampling_rate":[200]*12}

    def test_complete_row_metadata_and_seed_mapping(self):
        table=self.table()
        subjects,labels,channels,sessions,trials=check_metadata_table("SEED",table,expected_rows=12,expected_subjects=2,expected_classes=2)
        np.testing.assert_array_equal(sessions,["1","1","2","2","3","3"]*2)
        self.assertEqual(len(channels),60)
        for column,replacement in (("global_idx",list(reversed(table["global_idx"]))),
                                   ("sample_id",["same"]*12),("label_id",[0.1,1.0]*6),
                                   ("trial_id",["unverified"]*12),("session_id",[None]*12)):
            with self.assertRaises(ValueError):
                check_metadata_table("SEED",dict(table,**{column:replacement}),expected_rows=12,expected_subjects=2,expected_classes=2)
        bad=deepcopy(table);bad["channel_names_json"][1]=json.dumps([f"e{i}" for i in reversed(range(60))])
        with self.assertRaises(ValueError):check_metadata_table("SEED",bad,expected_rows=12,expected_subjects=2,expected_classes=2)

    def test_trial_identity_is_not_arbitrary_or_fractionally_truncated(self):
        np.testing.assert_array_equal(checked_trial_indices(["01","2",3]),[1,2,3])
        for values in ([None],[0.9],["stimulus_unknown"],["1.0"]):
            with self.assertRaises(ValueError):checked_trial_indices(values)

    def test_deap_valence_boundary_not_strict_greater_than(self):
        size=192;channels=json.dumps([f"e{i}" for i in range(60)])
        table={"sample_id":[f"s{i}" for i in range(size)],"subject_id":["s01"]*96+["s02"]*96,
               "label_id":[1]*96+[0]*96,"channel_names_json":[channels]*size,"global_idx":list(range(size)),
               "session_id":["1"]*size,"trial_id":["1"]*size,"aux_valence":[5.0]*96+[4.0]*96}
        check_metadata_table("DEAP",table,expected_rows=size,expected_subjects=2,expected_classes=2)
        bad=dict(table,label_id=[0]*size)
        with self.assertRaises(ValueError):check_metadata_table("DEAP",bad,expected_rows=size,expected_subjects=2,expected_classes=2)


class EvaluationTests(unittest.TestCase):
    def test_lp_scaling_uses_train_only_and_floor(self):
        values=np.array([[1,3],[3,3],[1000,900]],dtype=np.float32)
        mean,std=training_statistics(values,np.array([0,1]))
        np.testing.assert_array_equal(mean,[2,3]);np.testing.assert_allclose(std,[1,1e-6])
        values[2]=[-999,-999]
        other_mean,other_std=training_statistics(values,np.array([0,1]))
        np.testing.assert_array_equal(mean,other_mean);np.testing.assert_array_equal(std,other_std)

    def test_metrics_are_sample_balanced_not_plain_accuracy(self):
        metrics=sample_metrics([0]*9+[1],[0]*10,2)
        self.assertEqual(metrics["balanced_accuracy"],0.5);self.assertEqual(metrics["accuracy"],0.9)
        with self.assertRaises(ValueError):sample_metrics([0,1],[0,2],2)
        with self.assertRaises(ValueError):sample_metrics([0],[0],2)

    def test_epoch_selection_and_historical_relative_training_loss_stop(self):
        selector=EpochSelection()
        selected,stop=selector.observe(1,training_loss=1.0,validation_bacc=0.5)
        self.assertTrue(selected);self.assertFalse(stop)
        selected,stop=selector.observe(2,training_loss=0.995,validation_bacc=0.6)
        self.assertTrue(selected);self.assertEqual(selector.no_improvement,1)
        for epoch in range(3,12):
            _,stop=selector.observe(epoch,training_loss=0.995,validation_bacc=0.6)
        self.assertTrue(stop);self.assertEqual(selector.best_epoch,2)
        with self.assertRaises(ValueError):selector.observe(12,training_loss=float("nan"),validation_bacc=1)

    def test_common_method_lock_rejects_test_exposure_and_incomplete_rounds(self):
        def report(score,positive=3,cost=10):
            return {"test_evaluations":0,"validation_evaluations":72,"execution_valid":True,
                    "validation_summary":{"ft_macro_balanced_accuracy":score,"ft_positive_gain_datasets":positive},
                    "posttrain_wall_seconds":cost}
        self.assertEqual(select_method({1:report(0.7),2:report(0.6)}),1)
        self.assertEqual(select_method({1:report(0.7),2:report(0.7,4)}),2)
        self.assertEqual(select_method({1:report(0.7),2:report(0.7)}),1)
        bad=report(0.9);bad["test_evaluations"]=1
        with self.assertRaises(ValueError):select_method({1:report(0.7),2:bad})
        with self.assertRaises(ValueError):select_method({1:report(0.7)})

    def test_paired_bootstrap_constant_difference_and_input_shape(self):
        result=paired_bootstrap([0.6]*6,[0.5]*6)
        self.assertAlmostEqual(result["mean_delta"],0.1);self.assertAlmostEqual(result["lower"],0.1)
        self.assertAlmostEqual(result["upper"],0.1)
        self.assertEqual(result["resamples"],5000);self.assertEqual(result["seed"],20260713)
        with self.assertRaises(ValueError):paired_bootstrap([0.6]*5,[0.5]*5)

    def test_five_source_loss_and_gradients_equal_serial_reference(self):
        torch.manual_seed(7)
        tokens=torch.randn(5*8,2,2,3,requires_grad=True)
        actual,parts=separate_source_losses(tokens,torch.nn.Identity(),0.1,source_count=5,batch_size=8)
        expected=torch.stack([paired_info_nce(flatten_normalize(tokens[i*8:(i+1)*8]),temperature=0.1)[0] for i in range(5)]).mean()
        torch.testing.assert_close(actual,expected)
        gradient=torch.autograd.grad(actual,tokens,retain_graph=True)[0]
        expected_gradient=torch.autograd.grad(expected,tokens)[0]
        torch.testing.assert_close(gradient,expected_gradient)
        self.assertEqual(tuple(parts.shape),(5,))
        with self.assertRaises(ValueError):separate_source_losses(tokens[:39],torch.nn.Identity(),0.1,source_count=5,batch_size=8)

    def test_parameter_integer_and_schedule_boundaries(self):
        parameters={"posttrain_lr":1e-5,"temperature":0.1,"posttrain_weight_decay":1e-4,"warmup_epochs":3,"gradient_clip":1}
        validate_parameters(parameters)
        for bad in (dict(parameters,warmup_epochs=2.5),dict(parameters,posttrain_lr=0),dict(parameters,temperature=float("nan"))):
            with self.assertRaises(ValueError):validate_parameters(bad)
        self.assertAlmostEqual(learning_rate_multiplier(0,100,10),0.1)
        self.assertAlmostEqual(learning_rate_multiplier(10,100,10),1)
        self.assertAlmostEqual(learning_rate_multiplier(100,100,10),0)

    def test_cost_gate_preserves_forecast_and_rejects_insufficient_worker_time(self):
        from types import SimpleNamespace
        from throughput_plan import forecast
        smoke = {"posttrain_step_seconds":[0.2,0.1,0.1],"ft_batch128_step_seconds":[0.1,0.1],
                 "lp_head_batch128_step_seconds":[0.01,0.01],"lp_statistics_batch128_seconds":0.01,
                 "encoder_inference_batch128_seconds":0.02}
        releases = {"A":SimpleNamespace(labels=range(1000)),"B":SimpleNamespace(labels=range(2000))}
        folds = [{"train_n":256,"val_n":128}]*6
        probe = {"passed":True,"updates_completed":23,"timing":{"warmup_steps":3,"measured_steps":20,"step_seconds":[0.1]*20}}
        saved=[]
        with patch("throughput_plan.atomic_json",side_effect=lambda path,value:saved.append(value)), patch("throughput_plan.time.time",return_value=1000):
            baseline=forecast(smoke,releases,"A",folds,"baseline",deadline=2000,output="controlled-no-file")
            candidate=forecast(smoke,releases,"A",folds,"development",deadline=2000,output="controlled-no-file", training_probe=probe)
            self.assertEqual(baseline["components_seconds_before_margin"]["posttrain"],0)
            self.assertGreater(candidate["estimated_seconds"],baseline["estimated_seconds"])
            with self.assertRaises(TimeoutError):
                forecast(smoke,releases,"A",folds,"development",deadline=1001,output="controlled-no-file", training_probe=probe)
            self.assertFalse(saved[-1]["fits_worker_bound"])
            invalid=dict(smoke,encoder_inference_batch128_seconds=float("nan"))
            with self.assertRaises(ValueError):
                forecast(invalid,releases,"A",folds,"baseline",deadline=2000,output="controlled-no-file")

    def test_postlock_test_rejects_changed_initial_encoder_and_wrong_split_before_cuda(self):
        from types import SimpleNamespace
        from downstream import final_test_unit
        from evaluation_contract import EVALUATION_HASH
        release=SimpleNamespace(identity={"release":"controlled"})
        fold={"fold":0,"split_seed":42}
        identity={"release":release.identity,"fold":fold,"mode":"lp",
                  "evaluation_hash":EVALUATION_HASH,"initial_encoder_sha256":"a"*64}
        saved={"identity":identity,"initial_encoder_checkpoint":"controlled-encoder.pt"}
        lock={"complete_validation_rounds":[1,2],"selection_data":"validation_only","selected_round":2}
        with patch("downstream.verify_completion",return_value={"identity":identity}), \
             patch("downstream.read_json",return_value={"identity":identity}), \
             patch("downstream.torch.load",return_value=saved), \
             patch("downstream.sha256_file",return_value="b"*64), \
             patch("downstream.require_cuda") as cuda:
            with self.assertRaisesRegex(ValueError,"Initial encoder changed"):
                final_test_unit(release,fold,"lp","controlled-unit","controlled-output",method_lock=lock,device="cuda:0",deadline=2000)
            with self.assertRaisesRegex(ValueError,"release, split, mode"):
                final_test_unit(release,dict(fold,split_seed=43),"lp","controlled-unit","controlled-output",method_lock=lock,device="cuda:0",deadline=2000)
            cuda.assert_not_called()

    def test_final_summary_counts_216_calls_and_uses_one_locked_method(self):
        from analysis_contract import summarize_final
        from data_contract import TARGETS
        lock={"selected_round":2,"complete_validation_rounds":[1,2],"selection_data":"validation_only"}
        results={}
        for target in TARGETS:
            rows=[]
            for condition in ("R0","R1","R2"):
                score=0.5 if condition=="R0" else (0.6 if condition=="R1" else (0.4 if target=="DEAP" else 0.7))
                for mode in ("lp","ft"):
                    for fold in range(6):
                        rows.append({"identity":{"validation_unit":{"condition":{"condition":"R0_official_REVE" if condition=="R0" else condition}}},
                                     "mode":mode,"fold":fold,"target":target,"test_evaluations":1,
                                     "method_lock_hash":fingerprint(lock),
                                     "metrics":{"balanced_accuracy":score,"macro_f1":score,"accuracy":score}})
            results[target]={"phase":"final_test","method_lock_hash":fingerprint(lock),"test_evaluations":36,"tests":rows}
        report=summarize_final(results,lock,"controlled-no-artifacts")
        self.assertEqual(report["test_evaluations"],216)
        self.assertEqual(report["selected_common_condition"],"R2")
        self.assertFalse(report["performance_success"])
        self.assertEqual(report["ft_positive_gain_datasets"],5)
        self.assertAlmostEqual(report["equal_dataset_macro_summary"]["lp"]["R2"]["balanced_accuracy_mean"],0.65)
        self.assertAlmostEqual(report["tables"]["DEAP"]["ft"]["locked_candidate_paired_difference"]["mean_delta"],-0.1)
        bad=deepcopy(results);bad["DEAP"]["tests"].pop()
        with self.assertRaises(ValueError):summarize_final(bad,lock,"controlled-no-artifacts")


class BrokerAndSourceTests(unittest.TestCase):
    def request(self,phase="development",round_number=1):
        return build_request(job_dir="/controlled/RUN/experiments/job1",artifacts="/controlled/RUN/artifacts",phase=phase,target="SEED",
                             round_number=round_number,round_limit=2,
                             parameters={"posttrain_lr":1e-5,"temperature":0.1,"posttrain_weight_decay":1e-4,"warmup_epochs":3,"gradient_clip":1},
                             snapshot_hash="a"*64,plan_hash="b"*64)

    def test_broker_request_is_bounded_relative_and_does_not_publish(self):
        request=self.request()
        self.assertEqual(request["script"],"remote_worker.py");self.assertEqual(request["gpus"],6)
        self.assertEqual(request["timeout_seconds"],43200)
        validate_request(request,artifacts="/controlled/RUN/artifacts")
        for bad in (dict(request,credentials="forbidden"),dict(request,gpus=9),dict(request,script="../external.py")):
            with self.assertRaises(ValueError):validate_request(bad,artifacts="/controlled/RUN/artifacts")
        with self.assertRaises(ValueError):self.request("final_test",1)
        self.request("final_test",2)

    def test_receipt_requires_cloud_success_guarded_exit_and_matching_source(self):
        request=self.request()
        receipt={"status":"RUNNING","snapshot_hash":"a"*64,"gpus":6}
        self.assertFalse(check_receipt(receipt,request,"a"*64))
        receipt.update(status="SUCCESS",remote_result={"exit_code":0})
        self.assertTrue(check_receipt(receipt,request,"a"*64))
        for bad in (dict(receipt,snapshot_hash="b"*64),dict(receipt,remote_result={"exit_code":1}),
                    dict(receipt,status="REJECTED"),dict(receipt,status="SUBMISSION_UNRESOLVED")):
            with self.assertRaises((ValueError,RuntimeError)):check_receipt(bad,request,"a"*64)

    def test_exact_supplied_scheduler_builder_parameter_bindings_and_entrypoint_rejection(self):
        """Execute the actual supplied build_spec body in a pure virtual filesystem."""
        sources=read_json(ROOT/"validation_sources.json")
        entry=next(item for item in sources if item["path"].endswith("adapters.py"))
        self.assertEqual(sha256_file(ROOT/entry["path"]),entry["sha256"])
        tree=ast.parse((ROOT/entry["path"]).read_text())
        original=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=="SchedulerAdapter")
        selected=[node for node in original.body if isinstance(node,ast.FunctionDef) and node.name in {"__init__","build_spec"}]
        node=ast.ClassDef(name="SchedulerAdapter",bases=[],keywords=[],body=selected,decorator_list=[])
        template=read_json(ROOT/"job_spec.json")
        task=yaml.safe_load((ROOT/"task.yaml").read_text())
        names=set(task["research"]["source_files"])
        virtual_files={"/virtual/snapshot/source/"+name for name in names}
        class VirtualPath(PurePosixPath):
            def resolve(self):return VirtualPath(posixpath.normpath(str(self)))
            def is_file(self):return str(self.resolve()) in virtual_files
            def read_text(self):
                if str(self)=="/virtual/snapshot/source/job_spec.json":return json.dumps(template)
                raise ValueError("Unexpected virtual read")
        files=[{"path":name,"sha256":sha256_file(ROOT/name)} for name in sorted(names)]
        snapshot={"root":"/virtual/snapshot","source_root":str(ROOT),"files":files,"snapshot_hash":fingerprint(files),
                  "parameters":{name:bounds[1] for name,bounds in task["research"]["parameter_bounds"].items()},
                  "research_round":2,"research_round_limit":2}
        def verify(value):
            if fingerprint(value["files"])!=value["snapshot_hash"]:raise ValueError("Changed virtual manifest")
        namespace={"Path":VirtualPath,"json":json,"sys":sys,"deepcopy":deepcopy,"verify_snapshot":verify}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),entry["path"],"exec"),namespace)
        builder=namespace["SchedulerAdapter"]("/virtual/jobs","/virtual/scratch",task)
        actual=builder.build_spec("controlled_job",snapshot)
        self.assertEqual(actual["cwd"],"/virtual/snapshot/source")
        self.assertEqual(actual["research_round"],2);self.assertEqual(actual["research_round_limit"],2)
        self.assertEqual(actual["env"]["PYTHONPATH"],actual["cwd"])
        for name,location in task["research"]["parameter_bindings"].items():
            index=int(location.split(".")[-1])
            self.assertEqual(actual["submit"]["argv"][index],str(snapshot["parameters"][name]))
        template["run"]["argv"]=["python3","-B","../external.py"]
        with self.assertRaises(ValueError):builder.build_spec("bad",snapshot)
        template["run"]["argv"]=["bash","-c","true"]
        with self.assertRaises(ValueError):builder.build_spec("bad",snapshot)

    def test_exact_supplied_task_loader_accepts_complete_contract(self):
        entry=next(item for item in read_json(ROOT/"validation_sources.json") if item["path"].endswith("task_loader.py"))
        self.assertEqual(sha256_file(ROOT/entry["path"]),entry["sha256"])
        orchestration=next(item for item in read_json(ROOT/"validation_sources.json") if item["path"].endswith("orchestration.py"))
        self.assertEqual(sha256_file(ROOT/orchestration["path"]),orchestration["sha256"])
        from framework_reference.orchestration import normalize_orchestration
        tree=ast.parse((ROOT/entry["path"]).read_text())
        node=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=="load_task")
        namespace={"Path":Path,"yaml":yaml,"math":math,"normalize_orchestration":normalize_orchestration}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),entry["path"],"exec"),namespace)
        result=namespace["load_task"](ROOT/"task.yaml",ROOT)
        self.assertEqual(result["research"]["adapter"],"scheduler")
        from evaluation_contract import expected_test_calls
        limit = result["research"]["protocol"].get("valid_rounds", 2)
        self.assertEqual(result["research"]["expected_test_evaluations"],
                         {str(i): expected_test_calls(limit) if i == limit else 0 for i in range(1, limit + 1)})

    def test_no_test_predictions_in_development_and_final_method_lock_guard(self):
        tree=ast.parse((ROOT/"downstream.py").read_text())
        functions={node.name:node for node in tree.body if isinstance(node,ast.FunctionDef)}
        source=ast.get_source_segment((ROOT/"downstream.py").read_text(),functions["train_validation_unit"])
        self.assertNotIn('partitions["test"]',source)
        self.assertNotIn("final_test_unit(",source)
        # The final evaluator rejects missing lock before opening any state/data.
        from downstream import final_test_unit
        with self.assertRaises(ValueError):
            final_test_unit(None,None,"ft",ROOT,ROOT,method_lock={},device="cpu",deadline=1)

    def test_all_package_files_and_protected_contracts_are_declared(self):
        task=yaml.safe_load((ROOT/"task.yaml").read_text())
        contract=task["research"]
        names=contract["source_files"]
        self.assertEqual(len(names),len(set(names)))
        from package_inventory import package_files
        self.assertEqual(set(names),set(package_files(ROOT)))
        self.assertEqual(contract["validation_read_files"],[])
        for field in ("round_unit","baseline_plan","evaluation_policy"):
            self.assertIsInstance(read_json(ROOT/"readiness.json")[field],str)
            self.assertTrue(read_json(ROOT/"readiness.json")[field].strip())
        for name in names:
            self.assertTrue((ROOT/name).is_file(),name)
            self.assertFalse(Path(name).is_absolute() or ".." in Path(name).parts)
        protected={"validate.py","test_package.py","validate_core.py","job_spec.json","downstream.py","evaluation_contract.py","split_manifest.json","stages.py","broker_contract.py","source_parallel.py"}
        self.assertFalse(protected & set(contract["editable_files"]))
        self.assertEqual(set(contract["parameter_bounds"]),set(contract["allowed_variations"]))
        self.assertEqual(set(contract["parameter_bounds"]),set(contract["parameter_bindings"]))
        self.assertEqual(read_json(ROOT/"readiness.json")["unresolved"],[])
        template=read_json(ROOT/"job_spec.json")
        for stage in ("prepare","review","submit","run","analysis"):
            self.assertGreater(template[stage]["timeout_seconds"],0)
        self.assertGreater(template["estimated_seconds"],0);self.assertGreater(template["check_interval_seconds"],0)


class OneRoundCampaignTests(unittest.TestCase):
    """CPU fixtures exercise full scientific counts without claiming GPU results."""

    def test_one_round_selection_accepts_exactly_one_complete_validation_report(self):
        report = {"test_evaluations": 0, "validation_evaluations": 72, "execution_valid": True,
                  "validation_summary": {"ft_macro_balanced_accuracy": .6, "ft_positive_gain_datasets": 4},
                  "posttrain_wall_seconds": 100}
        self.assertEqual(select_method({1: report}, round_limit=1), 1)
        for bad in (dict(report, validation_evaluations=71), dict(report, test_evaluations=1)):
            with self.assertRaises(ValueError):
                select_method({1: bad}, round_limit=1)
        with self.assertRaises(ValueError):
            select_method({1: report})  # Default remains the original two-round contract.

    def test_one_round_final_summary_requires_all_144_actual_calls(self):
        from analysis_contract import summarize_final
        from data_contract import TARGETS
        lock = {"round_limit": 1, "selected_round": 1, "complete_validation_rounds": [1],
                "selection_data": "validation_only"}
        results = {}
        for target in TARGETS:
            rows = [{"identity": {"validation_unit": {"condition": {"condition": condition}}},
                     "mode": mode, "fold": fold, "target": target, "test_evaluations": 1,
                     "method_lock_hash": fingerprint(lock),
                     "metrics": {"balanced_accuracy": .5 + .1 * (condition == "R1"),
                                 "macro_f1": .5, "accuracy": .5}}
                    for condition in ("R0_official_REVE", "R1") for mode in ("lp", "ft") for fold in range(6)]
            results[target] = {"phase": "final_test", "method_lock_hash": fingerprint(lock),
                               "test_evaluations": 24, "tests": rows}
        report = summarize_final(results, lock, "controlled-no-artifacts")
        self.assertEqual(report["test_evaluations"], 144)
        self.assertEqual(report["selected_common_condition"], "R1")
        self.assertTrue(report["process_success"])
        self.assertEqual(report["ft_positive_gain_datasets"], 6)
        self.assertNotIn("R2", report["tables"]["DEAP"]["ft"])
        for change in ("missing", "duplicate", "test_exposed_lock"):
            bad = deepcopy(results)
            bad_lock = deepcopy(lock)
            if change == "missing": bad["DEAP"]["tests"].pop()
            elif change == "duplicate": bad["DEAP"]["tests"][-1] = bad["DEAP"]["tests"][0]
            else: bad_lock["selection_data"] = "test"
            with self.assertRaises(ValueError): summarize_final(bad, bad_lock, "controlled-no-artifacts")

    def test_one_round_broker_allows_post_lock_final_phase(self):
        request = build_request(job_dir="/controlled/RUN/experiments/job1", artifacts="/controlled/RUN/artifacts",
                                phase="final_test", target="SEED", round_number=1, round_limit=1,
                                parameters={"posttrain_lr": 1e-5, "temperature": .1, "posttrain_weight_decay": 1e-4,
                                            "warmup_epochs": 3, "gradient_clip": 1},
                                snapshot_hash="a"*64, plan_hash="b"*64)
        self.assertEqual(request["args"][request["args"].index("--research-round-limit") + 1], "1")

    def test_one_round_final_evaluator_passes_lock_gate_before_state_load(self):
        from downstream import final_test_unit
        class StateReached(Exception): pass
        lock = {"round_limit": 1, "selected_round": 1, "complete_validation_rounds": [1],
                "selection_data": "validation_only"}
        with patch("downstream.verify_completion", side_effect=StateReached):
            with self.assertRaises(StateReached):
                final_test_unit(None, None, "ft", ROOT, ROOT, method_lock=lock, device="cpu", deadline=1)

    def test_scheduler_one_round_locks_after_72_validation_units_then_tests(self):
        import tempfile
        from types import SimpleNamespace
        import stages
        from artifact_io import atomic_json
        from data_contract import TARGETS
        parameters = {"posttrain_lr": 1e-5, "temperature": .1, "posttrain_weight_decay": 1e-4,
                      "warmup_epochs": 3, "gradient_clip": 1}
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "new_run"
            artifacts, job = run / "artifacts", run / "experiments/job1"
            submission = job / "submit/output"
            manifest = {"snapshot_hash": "a" * 64, "files": []}
            atomic_json(submission / "submission.json", {"snapshot_hash": "a" * 64, "research_round": 1,
                        "artifacts": str(artifacts), "parameters": parameters, "plan_hash": "b" * 64,
                        "job_dir": str(job), "requests": [], "first_phase": "baseline", "baseline_reuse": None})
            conditions = {target: {"directory": str(artifacts / "baseline" / target)} for target in TARGETS}
            baseline = {target: {"baseline": conditions[target]} for target in TARGETS}
            candidates = {target: {"baseline": conditions[target],
                          "candidate": {"directory": str(artifacts / "conditions/R1" / target)}} for target in TARGETS}
            report = {"test_evaluations": 0, "validation_evaluations": 72, "execution_valid": True,
                      "snapshot_hash": "a" * 64, "protocol_gate": {"passed": True},
                      "validation_summary": {"ft_macro_balanced_accuracy": .6, "ft_positive_gain_datasets": 4},
                      "posttrain_wall_seconds": 100}
            args = SimpleNamespace(submit_output=str(submission), artifacts=str(artifacts), run_dir=str(job / "run"),
                                   research_round=1, research_round_limit=1, output=str(job / "analysis"))
            with patch.object(stages, "verify_source_snapshot", return_value=manifest), \
                 patch.object(stages, "task_contract", return_value={"research": {"protocol": {"valid_rounds": 1}}}), \
                 patch.object(stages, "check_plan", return_value={}), \
                 patch.object(stages, "enrich_report", side_effect=lambda report, **kwargs: report), \
                 patch.object(stages, "wait_phase", side_effect=[baseline, candidates, {}]) as waits, \
                 patch.object(stages, "publish_phase") as publishes, \
                 patch("analysis_contract.check_condition", return_value={}), \
                 patch("analysis_contract.summarize_validation", return_value=report), \
                 patch("analysis_contract.summarize_final", return_value={"test_evaluations": 144,
                       "performance_success": False, "process_success": True}):
                stages.run(args)
                stages.analysis(args)
            self.assertEqual(waits.call_count, 3)
            phases = [call.args[0][0]["args"][1] for call in publishes.call_args_list]
            self.assertEqual(phases, ["development", "final_test"])
            lock = read_json(artifacts / "final/method_lock.json")
            self.assertEqual(lock["complete_validation_rounds"], [1])
            self.assertEqual(lock["selected_round"], 1)
            self.assertEqual(set(read_json(artifacts / "final/evaluation_plan.json")["conditions"]["SEED"]), {"R0", "R1"})
            self.assertEqual(read_json(Path(args.output) / "report.json")["test_evaluations"], 144)
            cumulative = read_json(artifacts / "development/cumulative_validation.json")
            self.assertEqual(cumulative["test_evaluations"], 0)
            self.assertNotIn("final", cumulative["reports"][0])

    def test_forecast_one_round_final_counts_two_conditions(self):
        from throughput_plan import forecast
        from types import SimpleNamespace
        smoke = {"posttrain_step_seconds": [1, 1, 1], "ft_batch128_step_seconds": [1],
                 "lp_head_batch128_step_seconds": [1], "lp_statistics_batch128_seconds": 1,
                 "encoder_inference_batch128_seconds": 1}
        with patch("throughput_plan.atomic_json"), patch("throughput_plan.time.time", return_value=0):
            report = forecast(smoke, {"A": SimpleNamespace(labels=range(128)), "B": SimpleNamespace(labels=range(128))},
                              "A", [{"train_n": 128, "val_n": 128, "test_n": 128}], "final_test",
                              deadline=1000, output="controlled", round_limit=1)
        self.assertEqual(report["components_seconds_before_margin"],
                         {"feature_extraction": 2, "lp": 2, "ft": 2, "posttrain": 0})

    def test_configuration_binds_new_identity_rounds_and_scientific_counts(self):
        import tempfile
        import time
        from configure_launch import configure_package
        original = yaml.safe_load((ROOT / "task.yaml").read_text())
        for limit in (1, 2):
            with self.subTest(round_limit=limit), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "task.yaml").write_text(yaml.safe_dump(original))
                (root / "readiness.json").write_text((ROOT / "readiness.json").read_text())
                (root / "candidate_plan.json").write_text((ROOT / "candidate_plan.json").read_text())
                (root / "brief.md").write_text("Original immutable briefing remains available.\n")
                briefing = root / "authorized.md"
                briefing.write_text("Approved fresh REVE run; the requested round count takes precedence.\n")
                deadline = time.time() + 3600
                configure_package(root, run_id="fresh_reve", deadline=deadline, round_limit=limit, brief=briefing,
                                  max_cloud_tasks=48)
                configured = yaml.safe_load((root / "task.yaml").read_text())
                c = configured["research"]
                self.assertEqual(configured["task_id"], "fresh_reve")
                self.assertEqual(c["protocol"]["run_id"], "fresh_reve")
                self.assertEqual(c["protocol"]["resources"]["deadline"], deadline)
                self.assertEqual(c["protocol"]["posttrain"], original["research"]["protocol"]["posttrain"])
                self.assertEqual(c["protocol"]["split_manifest_sha256"], original["research"]["protocol"]["split_manifest_sha256"])
                self.assertEqual(c["requirements"]["min_valid_rounds"], limit)
                self.assertEqual(c["expected_test_evaluations"], {str(i): (72 * (limit + 1) if i == limit else 0)
                                                               for i in range(1, limit + 1)})
                self.assertEqual(c["protocol"]["resources"]["normal_worker_submissions"], 6 * (limit + 2))
                self.assertEqual(c["protocol"]["resources"]["preflight_worker_submissions"], 6 * (limit + 2))
                self.assertEqual(configured["research_prompt"], briefing.read_text())
                self.assertEqual((root / "historical_brief.md").read_text(), "Original immutable briefing remains available.\n")
                self.assertEqual((root / "brief.md").read_text(), briefing.read_text())
                self.assertEqual(c["protocol"]["brief_sha256"], sha256_file(briefing))
                self.assertEqual(set(c["source_files"]), {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()})
                self.assertEqual(c["requirements"]["continue_conditions"] == [], limit == 1)

    def test_lock_and_launch_inputs_reject_premature_or_invalid_contracts(self):
        from evaluation_contract import locked_round_limit, validate_round_limit
        for limit in (0, 3, True, 1.0, "1"):
            with self.assertRaises(ValueError): validate_round_limit(limit)
        valid = {"round_limit": 1, "selected_round": 1, "complete_validation_rounds": [1], "selection_data": "validation_only"}
        with self.assertRaises(ValueError): locked_round_limit(valid, expected=2)
        for change in ({"selected_round": 2}, {"complete_validation_rounds": []}, {"selection_data": "test"},
                       {"test_started_before_lock": True}):
            with self.assertRaises(ValueError): locked_round_limit(dict(valid, **change))



class WorkerEfficiencyTests(unittest.TestCase):
    def test_complete_formal_probe_keeps_training_budget_rng_and_timing_counts(self):
        from contextlib import nullcontext
        from types import SimpleNamespace
        import posttrain
        from data_contract import TARGETS
        class Encoder(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.scale = torch.nn.Parameter(torch.tensor(1.0))
            def forward(self, x, positions):
                return x * self.scale
        class Parallel(torch.nn.Module):
            device_ids = list(range(5))
            def __init__(self, model):
                super().__init__()
                self.model = model
            def forward(self, *args):
                self.last_replica_autocast = [{'replica_index':i,'autocast_enabled':True,
                                               'autocast_dtype':'torch.bfloat16'} for i in range(5)]
                return self.model(*args)
        class Builder:
            def __init__(self, **kwargs): pass
            def diagnostics(self): return {}
            def sample_batch(self, *, batch_size, rng):
                return torch.as_tensor(rng.integers(0, 100, size=batch_size))
        class Telemetry:
            def __init__(self, device):
                self.data_wait_seconds = self.h2d_seconds = self.samples = self.steps = self.step_seconds = 0
                self.utilization_samples = []
            def copy(self, values):
                event = SimpleNamespace(synchronize=lambda: None, elapsed_time=lambda other: 0.0)
                return torch.from_numpy(values), event, event
        rows_seen, reports = [], []
        def signals(rows):
            rows_seen.append(rows.copy())
            return (rows.astype(np.float32) / 100 + 1).reshape(-1, 1, 1)
        releases = {name: SimpleNamespace(labels=range(64*25), channel_names=[], subjects=[], sessions=[], trials=[],
                                          load_signals=signals) for name in TARGETS}
        parameters = {'posttrain_lr':1e-5,'temperature':0.1,'posttrain_weight_decay':1e-4,
                      'warmup_epochs':3,'gradient_clip':1}
        encoder = Encoder()
        with patch.object(Path, 'is_file', return_value=False), \
             patch.object(posttrain, 'require_cuda', return_value='cpu'), \
             patch.object(posttrain, 'stage_source_signals', return_value={}), \
             patch.object(posttrain, 'load_official', return_value=(encoder, torch.zeros(1,1,1), {'channel_names':[]})), \
             patch.object(posttrain, 'build_representation', return_value=torch.nn.Identity()), \
             patch.object(posttrain, 'parallel_model', side_effect=Parallel), \
             patch.object(posttrain, 'StimulusBatchBuilder', Builder), \
             patch.object(posttrain, 'Telemetry', Telemetry), \
             patch.object(posttrain, 'prepare_input', side_effect=lambda values: values), \
             patch.object(posttrain, 'separate_source_losses', side_effect=lambda tokens, *a: (tokens.square().mean(), torch.ones(5))), \
             patch.object(torch, 'autocast', side_effect=lambda *a, **k: nullcontext()), \
             patch.object(torch.cuda, 'synchronize'), \
             patch.object(posttrain, 'utilization', return_value={}), \
             patch.object(posttrain, 'atomic_json', side_effect=lambda path, report: reports.append(report)), \
             patch.object(posttrain, 'atomic_torch_save') as save_weights:
            report = posttrain.run_posttrain('FACED', releases, parameters, '/controlled/probe', device='cpu',
                                             identity={}, deadline=1e20, smoke_steps=23)
        self.assertEqual(report['updates_completed'],23)
        self.assertEqual(report['training_budget_steps'],40*25)
        self.assertEqual(report['timing']['warmup_steps'],3)
        self.assertEqual(report['timing']['measured_steps'],20)
        self.assertEqual(len(report['timing']['step_seconds']),20)
        self.assertTrue(all(value > 0 for value in report['timing']['step_seconds']))
        self.assertEqual(len(rows_seen),23*5)
        np.testing.assert_array_equal(rows_seen[0], np.random.default_rng(42+7919).integers(0,100,size=64))
        self.assertAlmostEqual(report['lr_after_last_update'],1e-5*posttrain.learning_rate_multiplier(23,1000,75))
        self.assertEqual(reports,[report])
        save_weights.assert_not_called()

    def test_actual_posttrain_entry_accepts_complete_probe_and_rejects_short_probe(self):
        from types import SimpleNamespace
        import posttrain
        from data_contract import TARGETS
        parameters = {'posttrain_lr': 1e-5, 'temperature': 0.1, 'posttrain_weight_decay': 1e-4,
                      'warmup_epochs': 3, 'gradient_clip': 1}
        releases = {name: SimpleNamespace(channel_names=[]) for name in TARGETS}
        with patch.object(Path, 'mkdir'), patch.object(Path, 'is_file', return_value=False), \
             patch.object(posttrain, 'seed_process'), patch.object(posttrain, 'require_cuda', return_value='cpu'), \
             patch.object(posttrain, 'stage_source_signals', return_value={}), \
             patch.object(posttrain, 'load_official', side_effect=RuntimeError('reached official loader')):
            with self.assertRaisesRegex(RuntimeError, 'reached official loader'):
                posttrain.run_posttrain('FACED', releases, parameters, '/controlled/probe', device='cpu',
                                        identity={}, deadline=1e20, smoke_steps=23)
            for steps in (0, 3, 8, 22, 24, True):
                with self.assertRaises(ValueError):
                    posttrain.run_posttrain('FACED', releases, parameters, '/controlled/probe', device='cpu',
                                            identity={}, deadline=1e20, smoke_steps=steps)

    def test_probe_measures_formal_training_before_forecast_and_preserves_evidence_on_failure(self):
        from types import SimpleNamespace
        import remote_worker
        import posttrain
        from data_contract import TARGETS
        calls, reports = [], {}
        releases = {name: SimpleNamespace(target=name, identity={'target': name},
                    preload_signals=lambda *args, **kwargs: {}) for name in TARGETS}
        args = SimpleNamespace(target='FACED', phase='development', research_round_limit=1)
        def formal(*args, **kwargs):
            calls.append('formal')
            self.assertEqual(kwargs['smoke_steps'], 23)
            return {'passed': True, 'timing': {'measured_steps': 20}}
        def forecast(*args, **kwargs):
            calls.append('forecast')
            self.assertEqual(kwargs['training_probe']['timing']['measured_steps'], 20)
            raise TimeoutError('controlled engineering review')
        with patch('release_io.Release.open', side_effect=lambda name: releases[name]), \
             patch('release_io.overlap_audit', return_value={}), \
             patch.object(remote_worker, 'atomic_json', side_effect=lambda path, value: reports.update({str(path): value})), \
             patch.object(remote_worker, 'read_json', return_value={'targets': {'FACED': {'folds': []}}}), \
             patch('cloud_smoke.smoke', side_effect=lambda *args, **kwargs: calls.append('numerical') or {'passed': True}), \
             patch.object(posttrain, 'run_posttrain', side_effect=formal), \
             patch('throughput_plan.forecast', side_effect=forecast):
            with self.assertRaises(TimeoutError):
                remote_worker.probe_workload(args, {}, Path('/controlled/output'), Path('/controlled/artifacts'), 1000)
        self.assertEqual(calls, ['numerical', 'formal', 'forecast'])
        self.assertIn('/controlled/output/data_preflight.json', reports)

    def test_available_memory_uses_container_limit(self):
        import posttrain
        files = {'/proc/meminfo': 'MemAvailable: 10000000 kB\n',
                 '/proc/self/cgroup': '0::/\n', '/sys/fs/cgroup/memory.max': '9000000',
                 '/sys/fs/cgroup/memory.current': '4000000'}
        with patch.object(Path, 'read_text', lambda path, *a, **k: files[str(path)]), \
             patch.object(Path, 'is_file', lambda path: str(path) in files):
            self.assertEqual(posttrain.available_memory_bytes(), 5000000)

    def test_ram_staging_rejects_invisible_cgroup_accounting(self):
        import posttrain
        files = {'/proc/meminfo': 'MemAvailable: 10000000 kB\n', '/proc/self/cgroup': '0::/\n'}
        with patch.object(Path, 'read_text', lambda path, *a, **k: files[str(path)]), \
             patch.object(Path, 'is_file', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'cgroup'):
                posttrain.available_memory_bytes()

    def test_available_memory_honors_finite_parent_when_leaf_is_unlimited(self):
        import posttrain
        files = {'/proc/meminfo': 'MemAvailable: 10000000 kB\n',
                 '/proc/self/cgroup': '0::/campaign/worker\n',
                 '/sys/fs/cgroup/campaign/worker/memory.max': 'max',
                 '/sys/fs/cgroup/campaign/worker/memory.current': '1000000',
                 '/sys/fs/cgroup/campaign/memory.max': '9000000',
                 '/sys/fs/cgroup/campaign/memory.current': '4000000'}
        with patch.object(Path, 'read_text', lambda path, *a, **k: files[str(path)]), \
             patch.object(Path, 'is_file', lambda path: str(path) in files):
            self.assertEqual(posttrain.available_memory_bytes(), 5000000)

    def test_broker_requests_six_gpus_and_rejects_any_other_count(self):
        artifacts = Path("/controlled/runs/test/artifacts")
        request = build_request(job_dir=artifacts.parent / "experiments/job1", artifacts=artifacts,
                                phase="development", target="FACED", round_number=1, round_limit=1,
                                parameters={"posttrain_lr":1e-5,"temperature":0.1,"posttrain_weight_decay":1e-4,
                                            "warmup_epochs":3,"gradient_clip":1},
                                snapshot_hash="a"*64, plan_hash="b"*64)
        self.assertEqual(request["gpus"], 6)
        for count in (1, 5, 7, 8):
            with self.assertRaises(ValueError):
                validate_request(dict(request, gpus=count), artifacts=artifacts)

    def test_ram_staging_preserves_rows_duplicates_and_restores_disk_cache(self):
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace
        import posttrain
        self.assertTrue(hasattr(posttrain, "stage_source_signals"), "Missing shared source RAM staging")
        with TemporaryDirectory() as temp:
            path = Path(temp) / "signals.npy"
            expected = np.arange(4*60*2000, dtype=np.float32).reshape(4,60,2000)
            np.save(path, expected)
            disk = np.load(path, mmap_mode="r")
            release = SimpleNamespace(labels=range(4), signal_cache=disk)
            with patch.object(posttrain, "available_memory_bytes", return_value=10**10):
                report = posttrain.stage_source_signals({"A":release}, ["A"], deadline=float("inf"))
                resident = release.signal_cache
                self.assertNotIsInstance(resident, np.memmap)
                self.assertFalse(resident.flags.writeable)
                np.testing.assert_array_equal(resident[[3,0,3,1]], expected[[3,0,3,1]])
                self.assertEqual(report["bytes"], expected.nbytes)
                posttrain.stage_source_signals({"A":release}, ["A"], deadline=float("inf"))
                self.assertIs(release.signal_cache, resident)
                posttrain.release_source_signals({"A":release})
                self.assertIs(release.signal_cache, disk)
                disk._mmap.close()

    def test_ram_staging_fails_before_allocating_if_memory_is_insufficient(self):
        from types import SimpleNamespace
        import posttrain
        self.assertTrue(hasattr(posttrain, "stage_source_signals"), "Missing bounded RAM staging")
        original = np.zeros((1,60,2000), dtype=np.float32)
        release = SimpleNamespace(labels=range(1), signal_cache=original)
        with patch.object(posttrain, "available_memory_bytes", return_value=1):
            with self.assertRaises(MemoryError):
                posttrain.stage_source_signals({"A":release}, ["A"], deadline=float("inf"))
        self.assertIs(release.signal_cache, original)

    def test_forecast_requires_formal_measurements_and_preserves_twelve_hour_gate(self):
        from types import SimpleNamespace
        from throughput_plan import forecast
        smoke = {"posttrain_step_seconds":[100,100,100],"ft_batch128_step_seconds":[0.1,0.1],
                 "lp_head_batch128_step_seconds":[0.01,0.01],"lp_statistics_batch128_seconds":0.01,
                 "encoder_inference_batch128_seconds":0.02}
        releases = {"A":SimpleNamespace(labels=range(1000)),"B":SimpleNamespace(labels=range(27340))}
        folds = [{"train_n":256,"val_n":128}]*6
        probe = {"passed":True, "updates_completed":23,
                 "timing":{"warmup_steps":3, "measured_steps":20, "step_seconds":[1.0]*20}}
        with patch("throughput_plan.atomic_json"), patch("throughput_plan.time.time", return_value=1000):
            with self.assertRaises(ValueError):
                forecast(smoke,releases,"A",folds,"development",deadline=87400,output="unused")
            report = forecast(smoke,releases,"A",folds,"development",deadline=87400,output="unused", training_probe=probe)
            self.assertEqual(report["measured_batch_seconds"]["posttrain_update"],1.0)
            self.assertLess(report["estimated_seconds"],43200)
            probe["timing"]["step_seconds"] = [2.0]*20
            with self.assertRaisesRegex(TimeoutError, "engineering review"):
                forecast(smoke,releases,"A",folds,"development",deadline=87400,output="unused", training_probe=probe)


if __name__=="__main__":
    unittest.main()
