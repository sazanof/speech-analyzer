# services/task_processor.py
import json
from threading import Thread, Lock
from queue import Queue
from typing import Optional, List
from datetime import datetime

from sqlalchemy import delete
from sqlmodel import select, col

from classes.logger import Logger
from database.database import write_session
from entities.conversation_entity import ConversationEntity
from models.recognizer_models import Utterance
from entities.dictionary_entity import DictionaryEntity
from entities.recording_entity import RecordingEntity
from entities.enums.recording_task_status import RecordingTaskStatus
from classes.text_analyzer import TextAnalyzer


class TaskProcessor:
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.task_queue = Queue()
        self.workers = []
        self.lock = Lock()
        self.analyzer = TextAnalyzer()
        self.is_running = True

        for i in range(max_workers):
            worker = Thread(target=self._worker, daemon=True, name=f"Worker-{i}")
            worker.start()
            self.workers.append(worker)

    def _worker(self):
        while self.is_running:
            try:
                task = self.task_queue.get()
                if task is None:
                    break

                self._process_task(task)
                self.task_queue.task_done()
            except Exception as e:
                Logger.err(f"Error in worker: {e}")

    def _process_task(self, recording_id: int):
        with write_session() as session:
            recording: Optional[RecordingEntity] = None

            try:
                recording = session.get(RecordingEntity, recording_id)
                if not recording:
                    Logger.err(f"Recording {recording_id} not found")
                    return

                if recording.analysis_status != RecordingTaskStatus.NEW:
                    Logger.warn(f"Recording {recording_id} has status {recording.analysis_status}, skipping")
                    return

                # Обновляем статус
                recording.analysis_status = RecordingTaskStatus.PENDING
                recording.analysis_start = datetime.now()
                session.add(recording)
                session.commit()
                session.refresh(recording)

                # Получаем словари из БД
                dictionaries: List[DictionaryEntity] = session.exec(select(DictionaryEntity)).all()
                dict_data = [{
                    "id": dict.id,
                    "name": dict.name,
                    "type": dict.type,
                    "phrases": dict.phrases,
                } for dict in dictionaries]

                # Анализируем разговор
                if recording.conversation:
                    # Преобразуем conversation в список Utterance
                    utterances: List[Utterance] = []
                    for item in recording.conversation:
                        utterance = Utterance(
                            speaker=item["speaker"],
                            text=item["text"],
                            start_time=item["start_time"],
                            end_time=item["end_time"]
                        )
                        utterances.append(utterance)

                    analysis_results = self.analyzer.analyze_conversation(utterances, dict_data)

                    Logger.info(f"Analysis results for recording {recording_id}")
                    for key, res in analysis_results.items():
                        if res.matched_phrases:
                            pass
                            # print(res.model_dump_json(indent=2))
                    conversation_with_highlights = self.analyzer.get_conversation_with_highlights(
                        utterances,
                        dict_data,
                        recording_id=recording.id
                    )
                    # Здесь можно сохранить результаты анализа в БД
                    # Например, добавить поле analysis_results в RecordingEntity
                    # recording.analysis_results = analysis_results.model_dump()

                    # TODO Clear all conversation results before
                    session.exec(
                        delete(ConversationEntity).where(col(ConversationEntity.recording_id) == recording.id)
                    )

                    for utterance_with_highlights in conversation_with_highlights:
                        conversation = ConversationEntity(**utterance_with_highlights.model_dump())
                        session.add(conversation)
                        # print(
                        #     f'[{utterance_with_highlights.start_time}] speaker: {utterance_with_highlights.speaker}, text: {utterance_with_highlights.text_with_highlights}')

                # Обновляем статус после завершения
                recording.analysis_status = RecordingTaskStatus.FINISHED
                recording.analysis_end = datetime.now()
                session.add(recording)
                session.commit()

            except Exception as e:
                Logger.err(f"Error processing recording {recording_id}: {e}")
                # В случае ошибки помечаем запись как FAILED
                if recording:
                    recording.analysis_status = RecordingTaskStatus.FAILED
                    recording.analysis_end = datetime.now()
                    session.add(recording)
                    session.commit()

    def add_task(self, recording_id: int):
        self.task_queue.put(recording_id)

    def fetch_new_tasks(self):
        with write_session() as session:
            try:
                recordings = session.exec(
                    select(RecordingEntity)
                    .where(RecordingEntity.recognize_status == RecordingTaskStatus.FINISHED)
                    .where(RecordingEntity.analysis_status == RecordingTaskStatus.NEW)
                    .limit(self.max_workers * 2)  # Берем в 2 раза больше задач, чем воркеров
                ).all()

                for recording in recordings:
                    self.add_task(recording.id)
            except Exception as e:
                Logger.err(f"Error fetching new tasks: {e}")

    def start_fetcher(self, interval: int = 30):
        def fetcher():
            while self.is_running:
                try:
                    with self.lock:
                        if self.task_queue.qsize() < self.max_workers:
                            self.fetch_new_tasks()
                except Exception as e:
                    Logger.err(f"Error in fetcher: {e}")

                import time
                time.sleep(interval)

        fetcher_thread = Thread(target=fetcher, daemon=True, name="TaskFetcher")
        fetcher_thread.start()

    def shutdown(self):
        self.is_running = False
        for _ in range(self.max_workers):
            self.task_queue.put(None)

        for worker in self.workers:
            worker.join()
