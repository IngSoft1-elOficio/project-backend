"""
Timer Manager para la ventana de Not So Fast.

Maneja timers asíncronos que pueden ser reiniciados o cancelados.
Cada timer está identificado por el nsf_action_id.
"""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class NSFTimer:
    """
    Representa un timer individual de Not So Fast.
    
    Attributes:
        room_id: ID de la sala
        nsf_action_id: ID de la acción NSF (YYY)
        initial_time: Tiempo inicial en segundos
        task: Tarea asyncio del countdown
        cancelled: Flag para saber si fue cancelado manualmente
    """
    
    def __init__(self, room_id: int, nsf_action_id: int, initial_time: int):
        self.room_id = room_id
        self.nsf_action_id = nsf_action_id
        self.initial_time = initial_time
        self.task: Optional[asyncio.Task] = None
        self.cancelled = False
        self.time_remaining = initial_time
    
    def cancel(self):
        """Cancela el timer manualmente."""
        self.cancelled = True
        if self.task and not self.task.done():
            self.task.cancel()
            logger.info(f"🛑 Timer cancelado para NSF action {self.nsf_action_id}")


class TimerManager:
    """
    Gestor global de timers de Not So Fast.
    
    Mantiene un diccionario de timers activos indexados por nsf_action_id.
    Permite iniciar, reiniciar y cancelar timers.
    """
    
    def __init__(self):
        self._timers: Dict[int, NSFTimer] = {}
        self._lock = asyncio.Lock()
    
    async def start_timer(
        self,
        room_id: int,
        nsf_action_id: int,
        time_remaining: int,
        on_tick_callback,
        on_complete_callback
    ):
        """
        Inicia un nuevo timer o reinicia uno existente.
        
        Args:
            room_id: ID de la sala
            nsf_action_id: ID de la acción NSF (identificador único del timer)
            time_remaining: Tiempo en segundos para contar
            on_tick_callback: Función async a llamar cada segundo
                             Signature: async def(room_id, nsf_action_id, time_remaining)
            on_complete_callback: Función async a llamar al terminar
                                 Signature: async def(room_id, nsf_action_id, was_cancelled)
        """
        async with self._lock:
            # Si ya existe un timer para esta acción, cancelarlo
            if nsf_action_id in self._timers:
                logger.info(f"🔄 Reiniciando timer para NSF action {nsf_action_id}")
                self._timers[nsf_action_id].cancel()
                # Esperar un momento para que se cancele completamente
                await asyncio.sleep(0.1)
            
            # Crear nuevo timer
            timer = NSFTimer(room_id, nsf_action_id, time_remaining)
            self._timers[nsf_action_id] = timer
            
            # Iniciar la tarea de countdown
            timer.task = asyncio.create_task(
                self._countdown(
                    timer,
                    on_tick_callback,
                    on_complete_callback
                )
            )
            
            logger.info(
                f"⏱️ Timer iniciado para NSF action {nsf_action_id} - "
                f"{time_remaining}s en room {room_id}"
            )
    
    async def _countdown(
        self,
        timer: NSFTimer,
        on_tick_callback,
        on_complete_callback
    ):
        """
        Ejecuta el countdown de un timer.
        
        Emite ticks cada segundo y llama al callback de completado al finalizar.
        """
        try:
            current_time = timer.initial_time
            
            # Countdown desde initial_time hasta 0
            while current_time > 0 and not timer.cancelled:
                timer.time_remaining = current_time
                
                # Emitir tick
                await on_tick_callback(
                    timer.room_id,
                    timer.nsf_action_id,
                    current_time
                )
                
                logger.debug(
                    f"⏱️ NSF action {timer.nsf_action_id} - "
                    f"{current_time}s restantes"
                )
                
                # Esperar 1 segundo
                await asyncio.sleep(1)
                current_time -= 1
            
            # Timer completado
            if not timer.cancelled:
                logger.info(
                    f"✅ Timer completado para NSF action {timer.nsf_action_id} - "
                    f"No hubo NSF, acción continúa"
                )
                await on_complete_callback(
                    timer.room_id,
                    timer.nsf_action_id,
                    was_cancelled=False
                )
            else:
                logger.info(
                    f"🛑 Timer cancelado para NSF action {timer.nsf_action_id} - "
                    f"NSF fue jugada"
                )
                await on_complete_callback(
                    timer.room_id,
                    timer.nsf_action_id,
                    was_cancelled=True
                )
        
        except asyncio.CancelledError:
            # Timer fue cancelado explícitamente (por cancel_timer())
            logger.info(f"🛑 Timer cancelado explícitamente para NSF action {timer.nsf_action_id}")
            # Llamar al callback de completado con was_cancelled=True
            await on_complete_callback(
                timer.room_id,
                timer.nsf_action_id,
                was_cancelled=True
            )
        
        except Exception as e:
            logger.error(
                f"❌ Error en countdown de NSF action {timer.nsf_action_id}: {e}"
            )
        
        finally:
            # Limpiar el timer del diccionario
            async with self._lock:
                if (timer.nsf_action_id in self._timers and 
                    self._timers[timer.nsf_action_id] == timer):  
                    del self._timers[timer.nsf_action_id]
    
    async def cancel_timer(self, nsf_action_id: int):
        """
        Cancela manualmente un timer.
        
        Args:
            nsf_action_id: ID de la acción NSF
        """
        async with self._lock:
            if nsf_action_id in self._timers:
                self._timers[nsf_action_id].cancel()
                logger.info(f"🛑 Timer cancelado manualmente para NSF action {nsf_action_id}")
            else:
                logger.warning(f"⚠️ No se encontró timer para NSF action {nsf_action_id}")
    
    def get_timer(self, nsf_action_id: int) -> Optional[NSFTimer]:
        """
        Obtiene un timer por su nsf_action_id.
        
        Returns:
            NSFTimer si existe, None si no
        """
        return self._timers.get(nsf_action_id)
    
    def is_timer_active(self, nsf_action_id: int) -> bool:
        """
        Verifica si existe un timer activo para una acción NSF.
        
        Returns:
            True si el timer existe y está activo
        """
        timer = self._timers.get(nsf_action_id)
        return timer is not None and not timer.cancelled


# Instancia global del TimerManager
_timer_manager: Optional[TimerManager] = None


def get_timer_manager() -> TimerManager:
    """
    Obtiene la instancia global del TimerManager (Singleton).
    
    Returns:
        TimerManager instance
    """
    global _timer_manager
    if _timer_manager is None:
        _timer_manager = TimerManager()
    return _timer_manager
