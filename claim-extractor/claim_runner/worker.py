"""Resource accounting for callbacks defined in each model's own run.py."""

import importlib.metadata
import json
import resource
import time
import traceback
from pathlib import Path

from .resources import GIB, write_json
from .outputs import write_outputs
from .runtime import generation_configuration


def probe(quantized: bool, destination: Path) -> int:
    import torch
    import transformers
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; no model weights were downloaded")
    x = torch.tensor([1., 2.], device="cuda", dtype=torch.float16)
    if (x * 2).tolist() != [2., 4.]:
        raise RuntimeError("FP16 CUDA operation failed")
    quantization = None
    if quantized:
        import bitsandbytes as bnb
        layer = bnb.nn.Linear4bit(64, 64, bias=False, compute_dtype=torch.float16,
                                 quant_type="nf4", compress_statistics=True).to("cuda")
        with torch.inference_mode():
            y = layer(torch.ones(1, 64, device="cuda", dtype=torch.float16))
        torch.cuda.synchronize()
        if not torch.isfinite(y).all().item():
            raise RuntimeError("NF4 CUDA operation produced nonfinite values")
        quantization = bnb.__version__
    write_json(destination, {"torch": torch.__version__, "transformers": transformers.__version__,
                             "bitsandbytes": quantization, "cuda": torch.version.cuda,
                             "gpu": torch.cuda.get_device_name(0),
                             "compute_capability": list(torch.cuda.get_device_capability(0)),
                             "total_vram_bytes": torch.cuda.get_device_properties(0).total_memory})
    return 0



def run(job_path, spec, load_model, prepare_chunks, infer):
    job = json.loads(Path(job_path).read_text(encoding='utf-8'))
    output = Path(job['output'])
    result = {'status':'running', 'mode':job['mode'], 'chunks_completed':0,
              'inference_seconds':0.0, 'truncated_chunks':0}
    started = time.perf_counter()
    phase = 'loading'
    load_started = inference_started = None

    def save():
        result['total_worker_seconds'] = time.perf_counter() - started
        times = resource.getrusage(resource.RUSAGE_SELF)
        result['process_cpu_seconds'] = times.ru_utime + times.ru_stime
        result['process_max_rss_bytes'] = times.ru_maxrss * 1024
        write_json(output / 'worker-result.json', result)

    def set_phase(value):
        nonlocal phase
        phase = value
        write_json(output / 'phase.json', {'phase':value})

    job['_stage'] = set_phase
    try:
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError('CUDA is unavailable')
        if job.get('seed') is not None:
            torch.manual_seed(job['seed'])
            torch.cuda.manual_seed_all(job['seed'])
        torch.set_num_threads(job['cpu_threads'])
        total = torch.cuda.get_device_properties(0).total_memory
        free, _ = torch.cuda.mem_get_info(0)
        budget = min(total, free) - job['gpu_reserve_bytes']
        if budget < GIB:
            raise RuntimeError('Insufficient VRAM after the configured reserve')
        torch.cuda.set_per_process_memory_fraction(budget / total, device=0)
        torch.backends.cuda.enable_flash_sdp(False)
        torch.cuda.reset_peak_memory_stats(0)
        result['versions'] = {name:importlib.metadata.version(name)
                              for name in ('torch','transformers','accelerate')}
        result['gpu'] = torch.cuda.get_device_name(0)
        result['gpu_budget_bytes'] = budget
        load_started = time.perf_counter()
        model, tokenizer = load_model(job)
        torch.cuda.synchronize()
        result['load_seconds'] = time.perf_counter() - load_started
        result['torch_load_peak_allocated_bytes'] = torch.cuda.max_memory_allocated(0)
        result['torch_load_peak_reserved_bytes'] = torch.cuda.max_memory_reserved(0)
        torch.cuda.reset_peak_memory_stats(0)
        save()
        set_phase('preparing')
        job['_generation'] = generation_configuration(model, spec.generation, job)
        chunks = prepare_chunks(job, model, tokenizer)
        result['chunks_expected'] = len(chunks)
        result['context_tokens'] = job['_context_limit']
        if job['_generation'] is not None:
            result['max_new_tokens'] = job['_generation'].max_new_tokens
        generation = job['_generation']
        result['configuration'] = {
            'sources':spec.sources,
            'generation':{**generation.to_diff_dict(), 'max_length':generation.max_length,
                          'max_new_tokens':generation.max_new_tokens, 'do_sample':generation.do_sample}
                         if generation is not None else {},
            'input':spec.input_configuration,
            'input_file':job['input']['path'], 'input_sha256':job['input']['sha256'],
            'input_partitioned':len(chunks) > 1,
            'repositories':[{'repo':r['repo'], 'revision':r['revision']} for r in job['repositories']],
            'hardware':{**spec.hardware_configuration, 'selected_precision':job['mode'],
                        'selected_dtype':'float32' if job['mode'] == 'fp32' else 'float16'},
            'overrides':{k:job[k] for k in ('max_new_tokens','max_length','context_tokens','seed') if job.get(k) is not None},
        }
        if job.get('prompt_file'):
            result['configuration']['prompt_file'] = job['prompt_file']
            result['configuration']['prompt_source'] = 'user-provided'
        if job.get('submission_file') or job.get('parent_comment_file'):
            result['configuration']['context_files'] = {k:job[k] for k in ('submission_file','parent_comment_file') if job.get(k)}
        save()
        blocks = []
        for index, chunk in enumerate(chunks, 1):
            print(f"{spec.alias}: chunk {index}/{len(chunks)} ({job['mode']})", flush=True)
            set_phase('inference')
            torch.cuda.synchronize()
            inference_started = time.perf_counter()
            with torch.inference_mode():
                raw, incomplete = infer(model, tokenizer, chunk, job)
            torch.cuda.synchronize()
            result['inference_seconds'] += time.perf_counter() - inference_started
            inference_started = None
            result['truncated_chunks'] += int(incomplete)
            blocks.append(raw)
            write_outputs(output, spec.output_format, blocks, chunk_count=len(chunks))
            result['chunks_completed'] += 1
            result['torch_inference_peak_allocated_bytes'] = torch.cuda.max_memory_allocated(0)
            result['torch_inference_peak_reserved_bytes'] = torch.cuda.max_memory_reserved(0)
            save()
        result['status'] = 'partial' if result['truncated_chunks'] else 'success'
        set_phase('finished')
        save()
        return 0 if result['status'] == 'success' else 1
    except Exception as exc:
        result.update(status='failed', error_type=type(exc).__name__, error=str(exc),
                      failure_phase=phase, error_traceback=traceback.format_exc())
        if load_started is not None and 'load_seconds' not in result:
            result['load_seconds'] = time.perf_counter() - load_started
        if inference_started is not None:
            result['inference_seconds'] += time.perf_counter() - inference_started
        try:
            import torch
            oom = isinstance(exc, torch.cuda.OutOfMemoryError)
            if torch.cuda.is_initialized():
                result['torch_failure_peak_allocated_bytes'] = torch.cuda.max_memory_allocated(0)
                result['torch_failure_peak_reserved_bytes'] = torch.cuda.max_memory_reserved(0)
        except Exception:
            oom = False
        result['retry_with_offload'] = oom or (job['mode'] == 'nf4' and phase.startswith('loading')
            and isinstance(exc, (RuntimeError, ValueError)))
        traceback.print_exc()
        save()
        return 42 if result['retry_with_offload'] else 1
