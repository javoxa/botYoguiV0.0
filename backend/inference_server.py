#!/usr/bin/env python3
"""
Servidor de inferencia con vLLM + FastAPI - Versión PRODUCCIÓN
Con control de concurrencia, backpressure y pooling de recursos
"""
import os
import logging
import asyncio
import time
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from vllm.engine.arg_utils import AsyncEngineArgs
from vllm.engine.async_llm_engine import AsyncLLMEngine
from vllm.sampling_params import SamplingParams
import uvicorn

# === CONFIGURACIÓN ===
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2-7B-Instruct-AWQ")#"Qwen/Qwen2-7B-Instruc"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 32))
QUEUE_TIMEOUT = float(os.getenv("QUEUE_TIMEOUT", 30.0))
MODEL_TIMEOUT = float(os.getenv("MODEL_TIMEOUT", 60.0))
KEEP_ALIVE_TIMEOUT = int(os.getenv("KEEP_ALIVE_TIMEOUT", 120))

# === LOGGING ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("vllm-server")

# === CONTROL DE CONCURRENCIA ===
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
request_queue = asyncio.Queue(maxsize=MAX_CONCURRENT_REQUESTS * 2)

# === INICIALIZAR vLLM ASÍNCRONO ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manejar el ciclo de vida de la aplicación"""
    logger.info("🚀 Inicializando vLLM asíncrono...")
    
    # Configuración optimizada para producción
    engine_args = AsyncEngineArgs(
        model=MODEL_NAME,
        quantization="awq",          # ← Obligatorio para AWQ( si no es GPTQ)
        dtype="float16",              # GPTQ-Int4 usa float16 para pesos no cuantizados
        trust_remote_code=True,       # ← Obligatorio para Qwen
        gpu_memory_utilization=0.85,  # Deja ~2.5 GB libres en A4000 (16 GB)
        max_model_len=4096,           # o 8192 si necesitas más
        enforce_eager=True,           # recomendado para GPUs de 16 GB
        enable_prefix_caching=True,
        max_num_seqs=MAX_CONCURRENT_REQUESTS,
        max_num_batched_tokens=4096,  # o 8192 si ajustas memoria
        tensor_parallel_size=1
        )
    
    app.state.engine = AsyncLLMEngine.from_engine_args(engine_args)
    logger.info("✅ vLLM inicializado correctamente")
    
    yield
    
    # Limpiar recursos
    logger.info("🛑 Apagando servidor vLLM...")
    try:
        await app.state.engine.shutdown()
    except Exception as e:
        logger.error(f"Error al apagar el motor: {e}")

app = FastAPI(
    title="UNSa LLM API", 
    version="2.0",
    lifespan=lifespan
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# === MODELOS DE DATOS ===
class InferenceRequest(BaseModel):
    prompt: str
    temperature: float = 0.2
    max_tokens: int = 850
    user_id: str = "anonymous"
    top_p: float = 0.9
    top_k: int = 50

class InferenceResponse(BaseModel):
    response: str
    model: str = MODEL_NAME
    tokens_used: int
    processing_time: float

# === MIDDLEWARE DE CONTROL DE CARGA ===
@app.middleware("http")
async def load_control_middleware(request: Request, call_next):
    """Control de carga y backpressure real"""
    if request_queue.qsize() >= request_queue.maxsize:
        logger.warning(f"🚨 Cola llena ({request_queue.qsize()}/{request_queue.maxsize}). Rechazando solicitud.")
        return JSONResponse(
            status_code=503,
            content={"error": "Servicio temporalmente saturado. Intenta nuevamente en unos minutos."}
        )
    
    start_time = time.time()
    
    try:
        # Agregar a cola con timeout
        task = asyncio.current_task()
        await asyncio.wait_for(request_queue.put(task), QUEUE_TIMEOUT)
        
        # Adquirir semáforo con timeout
        acquired = await asyncio.wait_for(semaphore.acquire(), QUEUE_TIMEOUT)
        if not acquired:
            raise asyncio.TimeoutError("Timeout adquiriendo recurso")
        
        try:
            response = await call_next(request)
        finally:
            semaphore.release()
            if not request_queue.empty():
                request_queue.get_nowait()
                request_queue.task_done()
        
        return response
        
    except asyncio.TimeoutError:
        logger.error("⏰ Timeout procesando solicitud")
        return JSONResponse(
            status_code=504,
            content={"error": "Tiempo de espera excedido. Tu solicitud es importante, intenta nuevamente."}
        )
    except Exception as e:
        logger.error(f"❌ Error en middleware: {e}")
        raise

# === ENDPOINT DE INFERENCIA OPTIMIZADO ===
@app.post("/generate", response_model=InferenceResponse)
async def generate(request: InferenceRequest):
    """Endpoint optimizado para chat interactivo - aprovecha continuous batching de vLLM"""
    start_time = time.time()
    
    try:
        logger.info(f"👤 [Usuario: {request.user_id}] Procesando solicitud...")
        
        sampling_params = SamplingParams(
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stop=["<|im_end|>", "</s>", "###"],
            repetition_penalty=1.1,
            skip_special_tokens=True,
            top_p=request.top_p,
            top_k=request.top_k
        )
        
        # Usar vLLM asíncrono - esto permite continuous batching REAL
        async def generate_with_timeout():
            results_generator = app.state.engine.generate(
                request.prompt,
                sampling_params,
                request_id=str(time.time()) + "_" + request.user_id
            )
            
            final_output = None
            async for request_output in results_generator:
                final_output = request_output
            
            return final_output
        
        # Ejecutar con timeout
        output = await asyncio.wait_for(generate_with_timeout(), MODEL_TIMEOUT)
        
        if not output or not output.outputs:
            raise ValueError("No se generó respuesta válida")
        
        response_text = output.outputs[0].text.strip()
        tokens_used = len(output.outputs[0].token_ids)
        processing_time = time.time() - start_time
        
        logger.info(f"✅ [Usuario: {request.user_id}] Respuesta generada ({tokens_used} tokens) en {processing_time:.2f}s")
        
        return InferenceResponse(
            response=response_text,
            tokens_used=tokens_used,
            processing_time=processing_time
        )
    
    except asyncio.TimeoutError:
        logger.error(f"⏰ [Usuario: {request.user_id}] Timeout en generación de texto")
        raise HTTPException(status_code=504, detail="Tiempo de generación excedido. Intenta con una pregunta más específica.")
    except Exception as e:
        logger.error(f"❌ [Usuario: {request.user_id}] Error en generación: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error procesando solicitud: {str(e)}")

# === HEALTH CHECK MEJORADO ===
@app.get("/health")
async def health_check():
    """Health check con información detallada de carga"""
    queue_load = request_queue.qsize() / request_queue.maxsize * 100 if request_queue.maxsize > 0 else 0
    semaphore_load = (MAX_CONCURRENT_REQUESTS - semaphore._value) / MAX_CONCURRENT_REQUESTS * 100
    
    status = "healthy" if queue_load < 80 and semaphore_load < 90 else "degraded"
    
    return {
        "status": status,
        "model": MODEL_NAME,
        "queue_size": request_queue.qsize(),
        "queue_max": request_queue.maxsize,
        "queue_load_percent": round(queue_load, 1),
        "concurrent_requests": MAX_CONCURRENT_REQUESTS - semaphore._value,
        "max_concurrent": MAX_CONCURRENT_REQUESTS,
        "semaphore_load_percent": round(semaphore_load, 1),
        "version": "2.0",
        "timestamp": time.time()
    }

if __name__ == "__main__":
    logger.info(f"🔧 Configuración: MAX_CONCURRENT_REQUESTS={MAX_CONCURRENT_REQUESTS}, MODEL_NAME={MODEL_NAME}")
    logger.info(f"🔌 Iniciando servidor en {HOST}:{PORT}")
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        timeout_keep_alive=KEEP_ALIVE_TIMEOUT,
        workers=1  # ¡Siempre 1 worker con vLLM! (no usar múltiples workers)
    )
