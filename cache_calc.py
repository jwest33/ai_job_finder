from dataclasses import dataclass


@dataclass
class HybridModelConfig:
    """Config for hybrid sliding/full attention models."""
    n_layers: int
    n_kv_heads: int
    head_dim: int
    sliding_window: int
    n_sliding_layers: int
    n_full_layers: int
    
    def kv_cache_bytes(self, context_length: int, bytes_per_value: float = 2.0) -> int:
        """Total KV cache size in bytes."""
        per_layer_per_token = 2 * self.n_kv_heads * self.head_dim * bytes_per_value
        
        sliding_tokens = min(context_length, self.sliding_window)
        sliding_bytes = int(self.n_sliding_layers * sliding_tokens * per_layer_per_token)
        full_bytes = int(self.n_full_layers * context_length * per_layer_per_token)
        
        return sliding_bytes + full_bytes


# Your model's config (extracted from JSON)
YOUR_MODEL = HybridModelConfig(
    n_layers=48,
    n_kv_heads=8,
    head_dim=256,
    sliding_window=1024,
    n_sliding_layers=40,  # Count of "sliding_attention" in layer_types
    n_full_layers=8,       # Count of "full_attention" in layer_types
)


def estimate_max_context(
    model_size_mb: float,
    vram_total_mb: int,
    config: HybridModelConfig,
    mmproj_size_mb: float = 0,
    vram_reserved_mb: int = 500,
    kv_quant_factor: float = 1.0,  # 0.5 for Q8, 0.25 for Q4
) -> dict:
    """Estimate maximum context for hybrid attention model."""
    
    available_mb = vram_total_mb - vram_reserved_mb - model_size_mb - mmproj_size_mb
    available_bytes = available_mb * 1024 * 1024
    
    # Binary search for max context that fits
    low, high = 1024, 131072
    max_context = low
    
    while low <= high:
        mid = (low + high) // 2
        kv_bytes = config.kv_cache_bytes(mid, bytes_per_value=2.0 * kv_quant_factor)
        
        if kv_bytes <= available_bytes:
            max_context = mid
            low = mid + 1
        else:
            high = mid - 1
    
    # Round to standard sizes
    standard_sizes = [2048, 4096, 8192, 16384, 32768, 65536, 131072]
    recommended = max((s for s in standard_sizes if s <= max_context), default=2048)
    conservative = max((s for s in standard_sizes if s <= max_context * 0.8), default=2048)
    
    # Calculate actual memory at recommended size
    kv_at_recommended = config.kv_cache_bytes(recommended, 2.0 * kv_quant_factor) / (1024**2)
    
    return {
        "vram_total_mb": vram_total_mb,
        "model_size_mb": model_size_mb,
        "mmproj_size_mb": mmproj_size_mb,
        "available_for_kv_mb": available_mb,
        "theoretical_max_context": max_context,
        "recommended_context": recommended,
        "conservative_context": conservative,
        "kv_cache_at_recommended_mb": kv_at_recommended,
    }


if __name__ == "__main__":
    # Gemma 3 12B Q8_0 ≈ 12.5 GB, mmproj ≈ 0.6 GB
    model_mb = 12_500
    mmproj_mb = 600
    
    print("\n" + "=" * 70)
    print("CONTEXT SIZE ESTIMATES FOR YOUR GEMMA 3 MODEL")
    print("=" * 70)
    print(f"Model: ~{model_mb/1024:.1f} GB | MMProj: ~{mmproj_mb/1024:.1f} GB")
    print(f"Architecture: {YOUR_MODEL.n_sliding_layers} sliding + {YOUR_MODEL.n_full_layers} full attention layers")
    print(f"Sliding window: {YOUR_MODEL.sliding_window} tokens")
    print()
    
    for vram_gb in [16, 24, 32, 48]:
        vram_mb = vram_gb * 1024
        
        print(f"\n{'─' * 70}")
        print(f"GPU: {vram_gb} GB VRAM")
        print(f"{'─' * 70}")
        
        for kv_type, kv_factor in [("FP16", 1.0), ("Q8_0", 0.5), ("Q4_0", 0.25)]:
            result = estimate_max_context(
                model_size_mb=model_mb,
                vram_total_mb=vram_mb,
                config=YOUR_MODEL,
                mmproj_size_mb=mmproj_mb,
                kv_quant_factor=kv_factor,
            )
            
            if result["available_for_kv_mb"] < 500:
                print(f"  KV {kv_type}: ❌ Insufficient VRAM (need more headroom)")
            else:
                print(f"  KV {kv_type}: recommended={result['recommended_context']:>6,} | "
                      f"conservative={result['conservative_context']:>6,} | "
                      f"KV cache={result['kv_cache_at_recommended_mb']:>5.0f} MB")
