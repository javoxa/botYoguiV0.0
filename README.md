# botYoguiV0.1
Bot no oficial del departamento de Física de UNSa
# Proyecto Bot IA – Validación de Tagging SQL con LLM

Este repositorio contiene un **prototipo funcional** de un sistema basado en **LLM (Large Language Model)** para la **clasificación y etiquetado semántico de consultas** orientadas a bases de datos SQL, con foco en **validar la calidad de los tags generados** a partir de interacciones reales de usuarios.

Esta primera versión aun no es apta para **escalar a producción** (se actualizará en versiones futuras), sino realizar **pruebas controladas con un número acotado de usuarios** para ajustar:
- prompts
- reglas de tagging
- estructura de consultas SQL generadas o asistidas por IA

---

## Objetivo del proyecto

- Evaluar la capacidad de un LLM (Qwen2) para:
  - interpretar consultas en lenguaje natural
  - asignar **tags semánticos estructurados**
  - facilitar la posterior traducción a SQL
- Validar estos tags mediante **uso real** (hasta ~50 usuarios pico)
- Iterar rápidamente sobre prompts y reglas sin costos de infraestructura de producción

---

## Arquitectura general

El proyecto está dividido en tres componentes principales:

### 1. Backend – Servidor de inferencia LLM
- Implementado con **FastAPI + vLLM**
- Soporta:
  - inferencia asíncrona
  - batching continuo
  - control de concurrencia y backpressure
- Diseñado para correr en GPU (local o cloud)

backend/
- "inference_server.py": servidor principal de inferencia, con un setup por defecto para una A4000 (en nube recomiendo rtx 3090)
- "descargar_qwen3.py": script auxiliar para descarga del modelo qwen2.5 instruct 7b q5 awq

---

### 2. Base de datos
- Esquema SQL versionado
- Migraciones iniciales
- Scripts de generación de SQL a partir de datasets estructurados

📁 database/
- schema/: definición de tablas e índices
- migrations: migraciones SQL de los prototipos iniciales y que se usaron para los .csv
- scripts de inicialización y generación de datos

⚠️ **Se incluyen datos reales de información pública, pero no dumps de producción**

---

### 3. Frontend / Bot
- Bot conversacional (Telegram)
- Conexión a PostgreSQL
- Uso del backend LLM para:
  - interpretación semántica
  - recuperación de información
  - asistencia en consultas

frontend/bot/
- lógica del bot
- retriever
- utilidades
- integración con base de datos

---

## Alcance del testing

Este repositorio está preparado para:

- Tests cortos
- Uso concurrente moderado (≤ 50 usuarios pico)
- Validación cualitativa y cuantitativa de:
  - tags SQL
  - consistencia semántica
  - errores frecuentes del modelo

**No está escalado para alta disponibilidad ni escalado horizontal**
Futuras versiones, traeran una estructura que permita el escalado a otras facultades. Esta primera instancia esta pensada en solo la Facultad de Ciencias Exactas

---

## Requisitos

- Python 3.10+
- GPU NVIDIA con soporte CUDA 12.x, este proyecto se desarrollo en una RTX A4000, se recomienda hardare igual o superior. Aunque con ajustes minimos (ver inference_server.py se puede utilizar hardware de arquitectura Ampere+ con menos VRAM (ej. RTX 3060).
- Docker (recomendado)
- PostgreSQL (local o contenedor)
- Drivers NVIDIA (560+) + CUDA (12.x) compatibles con vLLM

---

## Ejecución local (resumen)

1. Clonar el repositorio:

   git clone <repo_url>
   cd proyecto-bot-ia
   -ajustar parametros en .env (keys y demás)
   -levantar servicios
   docker-compose up --build
   -ó ejecutar manualmente
   python backend/inference_server.py
   ó
   python run_bot.py

