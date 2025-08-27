import time
from datetime import datetime
from queue import Queue
from threading import Event
from typing import Optional

from sqlmodel import select, asc

from classes.conversation_analyzer import ConversationAnalyzer
from classes.daemon import Daemon
from classes.logger import Logger
from database.database import write_session
from entities.enums.recording_task_status import RecordingTaskStatus
from entities.recording_entity import RecordingEntity
from models.recording_models import RecordingGet


class RecognizeThread:
    def __init__(self):
        self.task_queue = Queue()
        self.current_task: Optional[RecordingGet] = None
        self.shutdown_event = Event()
        self.watcher_thread: Optional[Daemon] = None
        self.worker_thread: Optional[Daemon] = None

    def _watch(self):
        """Поток для поиска новых задач и добавления их в очередь"""
        while not self.shutdown_event.is_set():
            try:
                self._fetch_new_tasks()
                time.sleep(5)
            except Exception as e:
                Logger.err(f"Error in watcher thread: {str(e)} {type(e)}")
                time.sleep(10)  # Подождать перед повторной попыткой

    def _worker(self):
        """Поток для обработки задач из очереди"""
        while not self.shutdown_event.is_set():
            try:
                if not self.task_queue.empty():
                    task = self.task_queue.get(timeout=5)
                    if task:
                        self._process_task(task)
                else:
                    Logger.debug('Waiting for new task')
                    time.sleep(5)
            except Exception as e:
                Logger.err(f"Error in worker thread: {str(e)}")

    def _fetch_new_tasks(self):
        """Поиск новых задач в базе данных"""
        with write_session() as session:
            # Получаем ID текущей задачи (если есть)
            current_task_id = self.current_task.id if self.current_task else None

            # Берем первую задачу в статусе PENDING, исключая текущую
            pending_task = session.exec(
                select(RecordingEntity)
                .where(
                    RecordingEntity.recognize_status == RecordingTaskStatus.PENDING.value,
                    RecordingEntity.id != current_task_id
                )
                .order_by(asc(RecordingEntity.created))
                .limit(1)
            ).first()

            if pending_task is not None:
                self._add_task_to_queue(pending_task)
            else:
                # Если нет PENDING, берем новую задачу, исключая текущую
                new_task = session.exec(
                    select(RecordingEntity)
                    .where(
                        RecordingEntity.recognize_status == RecordingTaskStatus.NEW.value,
                        RecordingEntity.id != current_task_id
                    )
                    .order_by(asc(RecordingEntity.created))
                    .limit(1)
                ).first()

                if new_task is not None:
                    self._add_task_to_queue(new_task)

    def _add_task_to_queue(self, db_record: RecordingEntity):
        """Добавляет задачу в очередь, но не меняет статус"""
        task = RecordingGet.model_validate(db_record.model_dump())
        self.task_queue.put(task)
        Logger.debug(f'Added task to queue: {task.id}, path: {task.path}')

    def _process_task(self, task: RecordingGet):
        """Обработка задачи распознавания"""
        self.current_task = task

        try:
            # Помечаем задачу как PENDING только когда начинаем обработку
            with write_session() as session:
                db_record = session.get(RecordingEntity, task.id)
                if not db_record:
                    Logger.err(f"Task not found in DB: {task.id}")
                    return

                if db_record.recognize_status != RecordingTaskStatus.NEW.value:
                    Logger.debug(f"Task {task.id} already in progress, skipping")
                    return

                db_record.recognize_status = RecordingTaskStatus.PENDING.value
                db_record.recognize_start = datetime.now()
                session.add(db_record)
                session.commit()

            Logger.debug(f'Starting recognition for task: {task.id}')

            analyzer = ConversationAnalyzer()
            analysis = analyzer.analyze(task.path)

            with write_session() as session:
                # Обновляем запись после завершения обработки
                db_record = session.get(RecordingEntity, task.id)
                if db_record:
                    db_record.duration = analysis.duration
                    db_record.conversation = [u.model_dump() for u in analysis.utterances]
                    db_record.recognize_end = datetime.now()
                    db_record.recognize_status = RecordingTaskStatus.FINISHED.value
                    db_record.analysis_status = RecordingTaskStatus.NEW.value # Analyte text again
                    session.add(db_record)
                    session.commit()

            analyzer.cleanup_temp_files()
            Logger.debug(f'Successfully processed task: {task.id}')

        except Exception as e:
            Logger.err(f"Error processing task {task.id}: {str(e)}")
            self._mark_task_as_failed(task.id)
        finally:
            self.current_task = None

    def _mark_task_as_failed(self, task_id: int):
        """Пометить задачу как завершенную с ошибкой"""
        with write_session() as session:
            db_record = session.get(RecordingEntity, task_id)
            if db_record:
                db_record.recognize_end = datetime.now()
                db_record.recognize_status = RecordingTaskStatus.FAILED.value
                session.add(db_record)
                session.commit()

    @staticmethod
    def _select_by_status(status: RecordingTaskStatus):
        return (select(RecordingEntity)
                .where(RecordingEntity.recognize_status == status.value)
                .order_by(asc(RecordingEntity.created)))

    def start(self):
        """Запуск потоков"""
        self.watcher_thread = Daemon(self._watch)
        self.worker_thread = Daemon(self._worker)
        Logger.info("Recognition threads started")

    def stop(self):
        """Остановка потоков"""
        self.shutdown_event.set()

        if self.current_task:
            Logger.info(f"Waiting for current task {self.current_task.id} to complete...")
            # Можно добавить таймаут для принудительной остановки

        if self.watcher_thread:
            self.watcher_thread.thread.join()
        if self.worker_thread:
            self.worker_thread.thread.join()

        Logger.info("Recognition threads stopped")

    def is_processing(self) -> bool:
        """Проверка, выполняется ли обработка задачи"""
        return self.current_task is not None


recognize_thread = RecognizeThread()