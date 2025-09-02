import time
from datetime import datetime
from queue import Queue
from threading import Event, Lock
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from sqlmodel import select, asc, col

from classes.conversation_analyzer import ConversationAnalyzer
from classes.daemon import Daemon
from classes.logger import Logger
from database.database import write_session
from entities.enums.recording_task_status import RecordingTaskStatus
from entities.recording_entity import RecordingEntity
from models.recording_models import RecordingGet


class RecognizeThread:
    def __init__(self, max_workers: int = 2):
        self.task_queue = Queue()
        self.current_tasks = {}  # Словарь для отслеживания выполняемых задач {task_id: task}
        self.shutdown_event = Event()
        self.watcher_thread: Optional[Daemon] = None
        self.worker_executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="RecognitionWorker"
        )
        self.lock = Lock()
        self.max_workers = max_workers

    def _watch(self):
        """Поток для поиска новых задач и добавления их в очередь"""
        while not self.shutdown_event.is_set():
            try:
                self._fetch_new_tasks()
                time.sleep(3)  # Уменьшили интервал проверки
            except Exception as e:
                Logger.err(f"Error in watcher thread: {str(e)} {type(e)}")
                time.sleep(10)

    def _fetch_new_tasks(self):
        """Поиск новых задач в базе данных"""
        with write_session() as session:
            # Получаем ID текущих выполняемых задач
            with self.lock:
                current_task_ids = list(self.current_tasks.keys())

            # Ищем задачи со статусом NEW, исключая текущие
            new_tasks = session.exec(
                select(RecordingEntity)
                .where(
                    RecordingEntity.recognize_status == RecordingTaskStatus.NEW.value,
                    col(RecordingEntity.id).not_in(current_task_ids) if current_task_ids else True
                )
                .order_by(asc(RecordingEntity.created))
                .limit(self.max_workers * 2)  # Берем больше задач чем воркеров
            ).all()

            for task in new_tasks:
                self._add_task_to_queue(task)

    def _add_task_to_queue(self, db_record: RecordingEntity):
        """Добавляет задачу в очередь"""
        task = RecordingGet.model_validate(db_record.model_dump())
        self.task_queue.put(task)
        Logger.debug(f'Added task to queue: {task.id}, path: {task.path}')

    def _process_task(self, task: RecordingGet):
        """Обработка задачи распознавания"""
        try:
            # Добавляем задачу в список выполняемых
            with self.lock:
                self.current_tasks[task.id] = task

            # Помечаем задачу как PENDING
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

            Logger.info(f'Starting recognition for task: {task.id}')

            # Выполняем распознавание
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
                    db_record.analysis_status = RecordingTaskStatus.NEW.value
                    session.add(db_record)
                    session.commit()

            analyzer.cleanup_temp_files()
            Logger.info(f'Successfully processed task: {task.id}')

        except Exception as e:
            Logger.err(f"Error processing task {task.id}: {str(e)}")
            self._mark_task_as_failed(task.id)
        finally:
            # Удаляем задачу из списка выполняемых
            with self.lock:
                if task.id in self.current_tasks:
                    del self.current_tasks[task.id]

    def _worker_loop(self):
        """Основной цикл обработки задач"""
        while not self.shutdown_event.is_set():
            try:
                if not self.task_queue.empty():
                    task = self.task_queue.get(timeout=2)
                    if task:
                        # Запускаем обработку в отдельном потоке
                        self.worker_executor.submit(self._process_task, task)
                else:
                    time.sleep(1)  # Короткая пауза если очередь пуста
            except Exception as e:
                Logger.err(f"Error in worker loop: {str(e)}")
                time.sleep(5)

    def _mark_task_as_failed(self, task_id: int):
        """Пометить задачу как завершенную с ошибкой"""
        with write_session() as session:
            db_record = session.get(RecordingEntity, task_id)
            if db_record:
                db_record.recognize_end = datetime.now()
                db_record.recognize_status = RecordingTaskStatus.FAILED.value
                session.add(db_record)
                session.commit()

    def start(self):
        """Запуск потоков"""
        self.watcher_thread = Daemon(self._watch)
        self.worker_thread = Daemon(self._worker_loop)
        Logger.info(f"Recognition threads started with {self.max_workers} workers")

    def stop(self):
        """Остановка потоков"""
        self.shutdown_event.set()

        # Останавливаем executor
        self.worker_executor.shutdown(wait=False, cancel_futures=True)

        if self.watcher_thread:
            self.watcher_thread.thread.join(timeout=5)
        if self.worker_thread:
            self.worker_thread.thread.join(timeout=5)

        Logger.info("Recognition threads stopped")

    def is_processing(self) -> bool:
        """Проверка, выполняется ли обработка задачи"""
        with self.lock:
            return len(self.current_tasks) > 0

    def get_active_tasks_count(self) -> int:
        """Возвращает количество активных задач"""
        with self.lock:
            return len(self.current_tasks)

    def get_queue_size(self) -> int:
        """Возвращает размер очереди задач"""
        return self.task_queue.qsize()


# Создаем экземпляр с 4 рабочими потоками
recognize_thread = RecognizeThread(max_workers=2)