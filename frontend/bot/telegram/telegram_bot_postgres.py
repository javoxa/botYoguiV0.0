#!/usr/bin/env python3
"""
Bot UNSA - VERSIÓN FINAL MODULAR
"""

import asyncio
import aiohttp
import hashlib
import time
import re
import signal
import sys
from collections import defaultdict
from typing import Optional

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Importaciones desde los módulos
from ..config import (
    TOKEN, DEBUG_MODE, INFERENCE_API_URL, DATABASE_URL,
    REQUEST_TIMEOUT, RETRY_ATTEMPTS, RETRY_DELAY,
    RATE_LIMIT_WINDOW, RATE_LIMIT_MAX_REQUESTS,
    logger
)
from ..models import ResponseMode, SearchResult
from ..utils import RateLimiter, anonymize_message, escape_md
from ..retriever import PostgresRetriever

class BotManager:
    def __init__(self, retriever: PostgresRetriever):
        self.retriever = retriever
        self.start_time = time.time()
        self.user_stats = {"messages": 0, "users": set()}
        self.last_message_time = {}
        self.limiter = RateLimiter(RATE_LIMIT_WINDOW, RATE_LIMIT_MAX_REQUESTS)
        self.session: Optional[aiohttp.ClientSession] = None
        self.stop_event = asyncio.Event()
        self.last_results_by_user = {}

    async def init_session(self):
        """Inicializa la sesión HTTP persistente"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT, connect=5)
            self.session = aiohttp.ClientSession(timeout=timeout)
            logger.info("✅ Sesión HTTP inicializada")

    async def close_session(self):
        """Cerrar sesión HTTP limpiamente"""
        if self.session and not self.session.closed:
            try:
                await self.session.close()
                logger.info("✅ Sesión HTTP cerrada")
            except Exception as e:
                logger.error("❌ Error al cerrar sesión HTTP: %s", str(e))

    async def close_resources(self):
        """Cierra todos los recursos limpiamente"""
        tasks = [
            self.close_session(),
            self.retriever.disconnect()
        ]

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("✅ Todos los recursos cerrados correctamente")
        except Exception as e:
            logger.error("❌ Error al cerrar recursos: %s", str(e))

    def signal_handler(self):
        """Manejador de señales para cierre limpio"""
        logger.info("🛑 Recibida señal de parada, cerrando recursos...")
        self.stop_event.set()

    def _build_prompt(self, question: str, context: str) -> str:
        """Construye el prompt para el LLM - RESTAURADO EXACTAMENTE"""
        return f"""Eres DptoFisicaUNSa, asistente oficial de la Universidad Nacional de Salta (UNSA).
INFORMACIÓN DE LA BASE DE DATOS UNSA:
{context}

INSTRUCCIONES:
1. Usa ÚNICAMENTE la información proporcionada arriba
2. NO inventes información bajo ninguna circunstancia
3. Sé conciso y directo (3-4 oraciones máximo)
4. Si la información no contiene lo solicitado, di que no tienes esa información específica
5. Incluye URLs o contactos si están en la información
6. Responde en español claro y profesional

PREGUNTA DEL USUARIO: {question}

RESPUESTA BREVE Y PRECISA:"""

    async def _call_llm(self, prompt: str, user_hash: str) -> str:
        """Llama al servicio de IA con reintentos automáticos"""
        max_retries = RETRY_ATTEMPTS
        base_delay = RETRY_DELAY

        for attempt in range(max_retries + 1):
            try:
                if self.session is None or self.session.closed:
                    await self.init_session()

                async with self.session.post(
                    INFERENCE_API_URL,
                    json={
                        "prompt": prompt,
                        "user_id": user_hash,
                        "max_tokens": 500,
                        "temperature": 0.2
                    }
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        answer = data.get("response", "").strip()
                        if answer:
                            return answer
                        logger.warning(f"Respuesta vacía de IA en intento {attempt+1}")
                    else:
                        logger.warning(f"Error HTTP {resp.status} en intento {attempt+1}")

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"Error de conexión en intento {attempt+1}: {e}")

            # Si no es el último intento, esperar antes de reintentar
            if attempt < max_retries:
                delay = base_delay * (attempt + 1)  # Backoff exponencial
                logger.info(f"Esperando {delay:.1f}s antes de reintento {attempt+2}/{max_retries+1}")
                await asyncio.sleep(delay)

        # Si todos los intentos fallan
        logger.error(f"Todos los intentos de conexión a IA fallaron para usuario {user_hash}")
        return ""

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # RESTAURADO: Mensaje exacto original
        await update.message.reply_text(
            "👋 *Bienvenido al Asistente UNSA*\n\n"
            "*¿En qué puedo ayudarte?*\n"
            "• Carreras y programas de estudio\n"
            "• Información sobre becas\n"
            "• Fechas de inscripción\n"
            "• Trámites administrativos\n"
            "• Contactos y ubicaciones\n\n"
            "*Comandos disponibles:*\n"
            "/help – Ver todos los comandos\n"
            "/stats – Estadísticas del bot\n"
            "/diagnose – Estado del sistema\n\n"
            "*Enlaces útiles:*\n"
            "🔗 https://www.unsa.edu.ar    \n"
            "🔗 https://exactas.unsa.edu.ar    ",
            parse_mode="Markdown"
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # RESTAURADO: Mensaje exacto original
        await update.message.reply_text(
            "🤖 *Asistente UNSA*\n\n"
            "*Comandos disponibles:*\n"
            "/start – Mensaje de bienvenida\n"
            "/help – Esta ayuda\n"
            "/stats – Estadísticas del bot\n"
            "/diagnose – Estado del sistema\n\n"
            "*También podés escribir tu consulta directamente.*\n"
            "Ejemplos:\n"
            "• \"¿Hay becas?\"\n"
            "• \"Carreras de ingeniería\"\n"
            "• \"Contacto de exactas\"\n"
            "• \"Fechas de inscripción 2026\"",
            parse_mode="Markdown"
        )

    # Para semántica
    EXPLANATORY_TRIGGERS = {
        "de que se trata",
        "de qué se trata",
        "de que se tratan",
        "diferencia",
        "me conviene",
        "salida laboral",
        "orientacion",
        "orientación",
        "perfil",
        "en que consiste",
        "qué hace"
    }

    def is_explanatory_question(self, msg: str) -> bool:
        msg = msg.lower()
        return any(t in msg for t in self.EXPLANATORY_TRIGGERS)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Verificar si debemos detener el procesamiento
        if self.stop_event.is_set():
            return

        msg = update.message.text.strip()
        user_id = update.effective_user.id

        # Rate limiting
        if not self.limiter.is_allowed(user_id):
            await update.message.reply_text(
                "⏳ Has excedido el límite de solicitudes. "
                "Por favor, espera unos minutos antes de volver a intentarlo."
            )
            return

        # Anti-spam: mínimo 1.5 segundos entre mensajes
        now = time.time()
        last = self.last_message_time.get(user_id, 0)
        if now - last < 1.5:
            return
        self.last_message_time[user_id] = now

        user_hash = hashlib.md5(str(user_id).encode()).hexdigest()[:8]
        self.user_stats["users"].add(user_hash)
        self.user_stats["messages"] += 1

        # Logging anónimo
        logger.info("📩 Usuario %s: %s", user_hash, anonymize_message(msg))

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )
        # ================= SALUDOS → IA DIRECTO =================

        GREETINGS = {"hola", "buenas", "buen", "hey", "saludos"}

        msg = update.message.text.strip()
        msg_norm = re.sub(r"[^\w\s]", "", msg.lower())
        tokens = msg_norm.split()

        is_greeting = any(t in GREETINGS for t in tokens)

        if is_greeting:
            prompt = f"""Eres DptoFisicaUNSa, asistente oficial de la Universidad Nacional de Salta (UNSA).

                    El usuario solo está saludando.

                        INSTRUCCIONES:
                                - Responde con un saludo breve y cordial (1 o 2 oraciones).
                                - Invita a hacer una consulta sobre becas, carreras, inscripciones o trámites.
                                - No inventes información.
                                - Usa español claro y profesional.

                                SALUDO DEL USUARIO: {msg}

                                RESPUESTA:"""

            answer = await self._call_llm(prompt, user_hash)

            if answer:
                await update.message.reply_text(answer)
            else:
                await update.message.reply_text(
                    "👋 Hola, soy el Asistente UNSA.\n\n"
                    "Podés preguntarme sobre becas, carreras, inscripciones o trámites.\n"
                    "Usá /help para ver los comandos."
                )

            return  # CORTA ACÁ, NO VA A LA BASE

        # ================= SEMÁNTICA SIN NUEVA BÚSQUEDA =================
        if self.is_explanatory_question(msg):
            prev_results = self.last_results_by_user.get(user_hash)

            if prev_results:
                careers_list = "\n".join(
                    f"- {r.content}" for r in prev_results)

                prompt = f"""Eres DptoFisicaUNSa, asistente oficial de la Universidad Nacional de Salta (UNSA).
                El usuario pide una explicación/orientación sobre carreras universitarias.
                Carreras disponibles:
                    {careers_list}

                    INSTRUCCIONES:
                        - Explicá brevemente de qué se trata cada carrera
                        - Marcá diferencias de enfoque (docencia, investigación, práctica)
                        - Orientá según intereses del estudiante
                        - NO inventes datos institucionales
                        - Usá un tono claro y orientativo
                        - Máximo 6–8 oraciones
                    PREGUNTA DEL USUARIO:
                        {msg}
                    RESPUESTA:"""

                answer = await self._call_llm(prompt, user_hash)
                if answer:
                    await update.message.reply_text(answer)
                    return

        #  Recién acá consultar la base
        context_text, results, mode = await self.retriever.retrieve(msg,limit=20)

        # Guardar resultados recientes si parecen carreras
        if results and any("Carrera" in r.content for r in results):
            self.last_results_by_user[user_hash] = results

        # Mejora la conversacion de carreras
        # ===== RESPUESTA SEMÁNTICA EXPLICATIVA =====
        if self.is_explanatory_question(msg):
            prev_results = self.last_results_by_user.get(user_hash)
            if prev_results:
                # --- NUEVA LÓGICA DE FILTRADO ---
                # Solo incluimos en la lista lo que coincida con palabras clave de la pregunta actual
                palabras_pregunta = set(msg.lower().split())

                filtered_careers = []
                for r in prev_results:
                    # Si el contenido de la carrera tiene alguna palabra de la pregunta (ej: "fisica")
                    # o si la pregunta es muy genérica ("de que se tratan?"), la incluimos.
                    if any(p in r.content.lower() for p in palabras_pregunta) or len(palabras_pregunta) < 4:
                        filtered_careers.append(r)

                # Si el filtro nos dejó vacíos, usamos los 3 primeros por las dudas
                if not filtered_careers:
                    filtered_careers = prev_results[:3]
                careers_list = "\n".join(f"- {r.content}" for r in filtered_careers)
                # --------------------------------

                prompt = f"""Eres DptoFisicaUNSa, asistente oficial de la Universidad Nacional de Salta (UNSA).
                El usuario realiza una consulta explicativa u orientativa sobre carreras universitarias.
                Carreras relacionadas.
                {careers_list}

                INSTRUCCIONES:
                    - Explicá brevemente de qué se trata cada carrera
                    - Indicá diferencias de enfoque si las hay
                    - Orientá al estudiante según intereses (docencia, investigación, práctica)
                    - No inventes información institucional específica
                    - Usá un tono claro y orientativo (máx. 6–8 oraciones)

                PREGUNTA DEL USUARIO:
                    {msg}
                RESPUESTA:"""
                answer = await self._call_llm(prompt, user_hash)
                if answer:
                    await update.message.reply_text(answer)
                    return

        if mode == ResponseMode.FALLBACK:
            await update.message.reply_text(
                "No tengo información específica sobre eso.\nVisitá https://www.unsa.edu.ar"
            )
            return

        #####Respuesta semantica de la IA a las carreras
        if mode == ResponseMode.DIRECT:
            #NUEVO: si es pregunta explicativa, usar IA
            if self.is_explanatory_question(msg):
                careers_list = "\n".join(
                    f"- {r.content}" for r in results
                    )
                prompt = f"""Eres DptoFisicaUNSa, asistente oficial de la Universidad Nacional de Salta (UNSA).
                El usuario hace una consulta explicativa/orientativa.
                Carreras encontradas:
                    {careers_list}

                    INSTRUCCIONES:
                        - Explicá brevemente de qué se trata cada carrera
                        - Indicá diferencias de enfoque si las hay
                        - Orientá al estudiante según intereses (docencia, investigación, práctica)
                        - No inventes información institucional específica
                        - Usá un tono claro y orientativo (máx. 6–8 oraciones)
                    PREGUNTA DEL USUARIO:
                        {msg}

                    RESPUESTA:"""

                answer = await self._call_llm(prompt, user_hash)

                if answer:
                    await update.message.reply_text(answer)
                    return
            #comportamiento original
            response = self.retriever.build_direct_response(results)
            await update.message.reply_text(response)
            return

        try:
            prompt = self._build_prompt(msg, context_text)
            answer = await self._call_llm(prompt, user_hash)

            if answer:
                await update.message.reply_text(answer)
                return

            # Si falló la IA, usar respuesta directa con notificación
            logger.info(f"Falló IA para usuario {user_hash}, usando fallback directo")
            fallback_response = (
                "⚠️ *Servicio de IA temporalmente no disponible*\n\n"
                f"{escape_md(self.retriever.build_direct_response(results))}\n\n"
                "_Información obtenida directamente de la base de datos_"
            )
            await update.message.reply_text(fallback_response, parse_mode="Markdown")

        except Exception as e:
            logger.error("❌ API error: %s", str(e))
            fallback_response = (
                "⚠️ *Ocurrió un error inesperado*\n\n"
                f"{escape_md(self.retriever.build_direct_response(results))}\n\n"
                "_Información obtenida directamente de la base de datos_"
            )
            await update.message.reply_text(fallback_response, parse_mode="Markdown")

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        r = self.retriever.stats

        uptime = time.time() - self.start_time
        hours, remainder = divmod(int(uptime), 3600)
        minutes, _ = divmod(remainder, 60)

        await update.message.reply_text(
            f"📊 *Estadísticas*\n\n"
            f"*Uptime:* {hours}h {minutes}m\n"
            f"*Base de datos:*\n"
            f"• Consultas: {r['queries']}\n"
            f"• Fragmentos: {r['fragments']}\n"
            f"• Errores: {r['errors']}\n\n"
            f"*Usuarios:*\n"
            f"• Únicos: {len(self.user_stats['users'])}\n"
            f"• Mensajes: {self.user_stats['messages']}\n\n"
            f"*Rate Limit:* {RATE_LIMIT_MAX_REQUESTS} solicitudes por {RATE_LIMIT_WINDOW} segundos",
            parse_mode="Markdown"
        )

    async def diagnose(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        r = self.retriever.stats

        db_status = "🟢 Conectado" if self.retriever.connected else "🔴 Error"
        ia_status = "🟢 OK"

        try:
            if self.session is None or self.session.closed:
                await self.init_session()

            # Construir URL de health basada en la variable de entorno
            base_url = INFERENCE_API_URL.rsplit('/', 1)[0]
            health_url = f"{base_url}/health"

            async with self.session.get(health_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    status_msg = data.get("status", "unknown")
                    queue_load = data.get("queue_load_percent", 0)
                    ia_status = f"🟢 {status_msg} - {queue_load}% cola"
                else:
                    ia_status = f"🔴 Error HTTP {resp.status}"
        except Exception as e:
            ia_status = f"🔴 Sin conexión: {str(e)[:50]}"

        await update.message.reply_text(
            "🩺 *Diagnóstico del sistema*\n\n"
            f"*PostgreSQL:* {db_status}\n"
            f"• Fragmentos: {r['fragments']}\n\n"
            f"*Servicio de IA:* {ia_status}\n\n"
            f"*Modo debug:* {'🟢 ON' if DEBUG_MODE else '⚫ OFF'}\n"
            f"*Rate limit:* {RATE_LIMIT_MAX_REQUESTS} solicitudes/{RATE_LIMIT_WINDOW}s\n"
            f"*Timeout IA:* {REQUEST_TIMEOUT}s",
            parse_mode="Markdown"
        )

# ==================== MAIN ====================

async def main_async():
    # Registrar manejador de señales para cierre limpio
    loop = asyncio.get_running_loop()
    manager = None

    try:
        # Inicializar componentes
        retriever = PostgresRetriever(DATABASE_URL, debug_mode=DEBUG_MODE)
        manager = BotManager(retriever)

        # Registrar señales de sistema
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, manager.signal_handler)

        # Conectar a bases de datos y servicios
        await asyncio.gather(
            retriever.connect(),
            manager.init_session(),
            return_exceptions=True
        )

        app = Application.builder().token(TOKEN).build()

        app.add_handler(CommandHandler("start", manager.start))
        app.add_handler(CommandHandler("help", manager.help))
        app.add_handler(CommandHandler("stats", manager.stats))
        app.add_handler(CommandHandler("diagnose", manager.diagnose))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manager.handle_message))

        logger.info("🤖 Bot UNSA iniciado correctamente")
        logger.info("💡 Usa /diagnose para verificar el estado del sistema")

        # Iniciar polling
        async with app:
            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)

            # Esperar señal de parada
            await manager.stop_event.wait()

            # Cerrar recursos
            await app.updater.stop()
            await app.stop()
            await app.shutdown()

    except Exception as e:
        logger.error("❌ Error fatal en main_async: %s", str(e))
        if DEBUG_MODE:
            import traceback
            logger.debug("Traceback: %s", traceback.format_exc())
    finally:
        # Asegurar cierre limpio de recursos
        if manager:
            await manager.close_resources()

def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("👋 Bot detenido por el usuario")
    except Exception as e:
        logger.error("❌ Error fatal: %s", str(e))
        if DEBUG_MODE:
            import traceback
            logger.debug("Traceback: %s", traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
