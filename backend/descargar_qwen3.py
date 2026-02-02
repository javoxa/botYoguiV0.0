#!/usr/bin/env python3
"""
Script para descargar el modelo Qwen2-7B-Instruct-AWQ
Ejecutar ANTES de iniciar el servidor
"""
import os
from vllm import LLM

MODEL_NAME = "Qwen/Qwen2-7B-Instruct-AWQ"
MODEL_DIR = os.getenv("MODEL_DIR", "./models")

print(f"📥 Descargando modelo {MODEL_NAME}...")
print(f"💾 Guardando en: {MODEL_DIR}")

os.makedirs(MODEL_DIR, exist_ok=True)

llm = LLM(
    model=MODEL_NAME,
    download_dir=MODEL_DIR,
    quantization="AWQ",  # Reemplaza GPTQ con AWQ (mejor soporte)
    dtype="float16",
    trust_remote_code=True,
    gpu_memory_utilization=0.9
)

print("✅ ¡Modelo descargado correctamente!")
print(f"💡 Para usarlo: export MODEL_DIR={MODEL_DIR} antes de iniciar el servidor")
