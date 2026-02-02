import asyncio
import time
import re
import logging
from typing import List, Tuple
import asyncpg

from .models import SearchResult, ResponseMode
from .config import logger

class PostgresRetriever:
    def __init__(self, db_url: str, debug_mode: bool = False):
        self.db_url = db_url
        self.pool = None
        self.connected = False
        self.debug_mode = debug_mode

        self.stats = {
            "queries": 0,
            "errors": 0,
            "fragments": 0
        }

        self.last_connect_attempt = 0
        self.connect_retry_delay = 2  # segundos entre reintentos

    async def connect(self) -> bool:
        """Intentar conectar a PostgreSQL con reintentos"""
        current_time = time.time()

        # Evitar intentos frecuentes si falló recientemente
        if current_time - self.last_connect_attempt < self.connect_retry_delay:
            return self.connected

        self.last_connect_attempt = current_time

        if self.connected:
            return True

        try:
            self.pool = await asyncpg.create_pool(
                self.db_url,
                min_size=2,
                max_size=20,
                command_timeout=30
            )

            async with self.pool.acquire() as conn:
                if self.debug_mode:
                    try:
                        await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
                    except Exception as e:
                        logger.warning(f"Advertencia al crear extensión pg_trgm: {e}")

                self.stats["fragments"] = await conn.fetchval(
                    "SELECT COUNT(*) FROM fragmentos_conocimiento"
                )

            self.connected = True
            logger.info("✅ PostgreSQL conectado | Fragmentos: %d", self.stats["fragments"])
            return True

        except Exception as e:
            self.connected = False
            logger.error("❌ PostgreSQL error: %s", str(e))
            return False

    async def disconnect(self):
        """Cerrar conexión pool al apagar"""
        if self.pool:
            try:
                await self.pool.close()
                self.connected = False
                logger.info("✅ Pool PostgreSQL cerrado")
            except Exception as e:
                logger.error("❌ Error al cerrar pool PostgreSQL: %s", str(e))

    def _clean_query_terms(self, query: str) -> List[str]:
        """Limpia la consulta y extrae términos de búsqueda"""
        clean = re.sub(r"[^\w\s]", "", query.lower())
        words = clean.split()
        stopwords = {'hay', 'que', 'de', 'la', 'el', 'los', 'las', 'un', 'una', 'unos', 'unas',
                    'para', 'por', 'con', 'sin', 'sobre', 'bajo', 'entre', 'hacia', 'desde'}
        terms = [w for w in words if len(w) >= 3 and w not in stopwords]

        if not terms and len(clean) >= 4:
            return [clean[:20]]

        return terms[:3] if terms else []

    async def retrieve(
        self, query: str, limit: int = 6
    ) -> Tuple[str, List[SearchResult], ResponseMode]:

        self.stats["queries"] += 1

        # Intentar conectar con reintentos automáticos
        if not await self.connect():
            await asyncio.sleep(1)
            if not await self.connect():
                return "Error de base de datos.", [], ResponseMode.FALLBACK

        try:
            terms = self._clean_query_terms(query)

            async with self.pool.acquire() as conn:
                if not terms:
                    rows = await conn.fetch(
                        """
                        SELECT id, contenido, categoria, facultad, palabras_clave
                        FROM fragmentos_conocimiento
                        ORDER BY usado_count DESC
                        LIMIT $1
                        """,
                        limit
                    )
                else:
                    # SOLUCIÓN SEGURA: Usar parámetros posicionales para evitar SQL Injection
                    similarity_conditions = []
                    ilike_conditions = []
                    keyword_conditions = []
                    params = []

                    for i, term in enumerate(terms):
                        # ILIKE condition
                        ilike_conditions.append(f"contenido ILIKE ${len(params) + 1}")
                        params.append(f"%{term}%")

                        # Similarity condition
                        similarity_conditions.append(f"similarity(contenido, ${len(params) + 1}::text) > 0.3")
                        params.append(term)

                        # Keyword condition
                        keyword_conditions.append(f"${len(params) + 1} = ANY(palabras_clave)")
                        params.append(term)

                    # Combinar todas las condiciones
                    all_conditions = ilike_conditions + similarity_conditions + keyword_conditions

                    # Añadir parámetros para ORDER BY y LIMIT
                    params.append(terms[0])  # Para el similarity en ORDER BY
                    similarity_param_index = len(params)
                    params.append(limit)

                    sql = f"""
                        SELECT id, contenido, categoria, facultad, palabras_clave
                        FROM fragmentos_conocimiento
                        WHERE {' OR '.join(all_conditions)}
                        ORDER BY
                          GREATEST(similarity(contenido, ${similarity_param_index}::text), 0) DESC,
                          usado_count DESC
                        LIMIT ${similarity_param_index + 1}
                    """

                    rows = await conn.fetch(sql, *params)

                if not rows:
                    return "No se encontró información.", [], ResponseMode.FALLBACK

                results = [
                    SearchResult(
                        id=r["id"],
                        content=r["contenido"],
                        category=r["categoria"],
                        faculty=r["facultad"],
                        score=1.0,
                        keywords=r["palabras_clave"] or []
                    )
                    for r in rows
                ]

                for r in results:
                    await conn.execute(
                        "UPDATE fragmentos_conocimiento SET usado_count = usado_count + 1 WHERE id = $1",
                        r.id
                    )

                context = "\n".join(r.content for r in results)
                total_len = sum(len(r.content) for r in results)

                # RESTAURADO: Umbral original de 800 caracteres
                mode = ResponseMode.DIRECT if total_len < 800 else ResponseMode.LLM
                return context, results, mode

        except Exception as e:
            self.stats["errors"] += 1
            logger.error("❌ Retrieve error: %s", str(e))
            return "Error consultando la base.", [], ResponseMode.FALLBACK

    def build_direct_response(self, results: List[SearchResult]) -> str:
        if not results:
            return "No encontré información específica."
        # ❌ NO escapar contenido de la base
        return "\n\n".join(r.content for r in results[:3])
