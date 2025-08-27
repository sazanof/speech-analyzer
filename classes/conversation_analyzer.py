import os
import time
import tempfile
import requests
from datetime import timedelta
from typing import List, Union
import whisper
from pydub import AudioSegment
from urllib.parse import urlparse

from models.recognizer_models import Utterance, ConversationAnalysis


class ConversationAnalyzer:
    def __init__(self, model_name: str = "large"):
        if not os.path.exists('./tmp'):
            os.makedirs('./tmp', mode=0o755, exist_ok=True)
        """
        Инициализация анализатора разговоров.

        :param model_name: Название модели Whisper (по умолчанию "large")
        """
        self.model = whisper.load_model(model_name)
        self.temp_files = []  # Для хранения путей временных файлов

    def __del__(self):
        """Удаление временных файлов при уничтожении объекта."""
        self.cleanup_temp_files()

    def cleanup_temp_files(self):
        """Удаляет все временные файлы, созданные экземпляром класса."""
        for file_path in self.temp_files:
            try:
                os.remove(file_path)
            except:
                pass
        self.temp_files = []

    def _download_from_url(self, url: str) -> str:
        """Скачивает файл по URL во временный файл и возвращает путь к нему."""
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()

            # Создаем временный файл с правильным расширением
            parsed_url = urlparse(url)
            ext = os.path.splitext(parsed_url.path)[1] or '.mp3'
            temp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            temp_path = temp_file.name

            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_file.close()

            self.temp_files.append(temp_path)
            return temp_path
        except Exception as e:
            raise RuntimeError(f"Ошибка загрузки файла по URL: {e}")

    def _ensure_local_file(self, audio_source: Union[str, bytes]) -> str:
        """Обеспечивает наличие локального файла, обрабатывая как пути, так и URL."""
        if isinstance(audio_source, bytes):
            # Если переданы байты, создаем временный файл
            temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
            temp_path = temp_file.name
            temp_file.write(audio_source)
            temp_file.close()
            self.temp_files.append(temp_path)
            return temp_path
        elif audio_source.startswith(('http://', 'https://')):
            # Если это URL, скачиваем файл
            return self._download_from_url(audio_source)
        else:
            # Если это локальный путь, просто возвращаем его
            return audio_source

    def split_stereo_audio(self, audio_path: str) -> tuple[str, str]:
        """Разделяет стерео аудиофайл на два монофайла (левый и правый каналы)."""
        # Поддерживаемые форматы
        if audio_path.lower().endswith('.mp3'):
            audio = AudioSegment.from_mp3(audio_path)
        elif audio_path.lower().endswith('.wav'):
            audio = AudioSegment.from_wav(audio_path)
        else:
            raise ValueError("Поддерживаются только MP3 и WAV файлы")

        # Создаем уникальные имена файлов
        timestamp = int(time.time() * 1000)

        # Левый канал (клиент)
        left_channel = audio.split_to_mono()[0]
        left_path = f"./tmp/temp_left_{timestamp}.wav"
        left_channel.export(left_path, format="wav")
        self.temp_files.append(left_path)

        # Правый канал (оператор)
        right_channel = audio.split_to_mono()[1]
        right_path = f"./tmp/temp_right_{timestamp}.wav"
        right_channel.export(right_path, format="wav")
        self.temp_files.append(right_path)

        return left_path, right_path

    def transcribe_audio(self, audio_path: str) -> list[dict]:
        """Транскрибирует аудиофайл с помощью Whisper и возвращает сегменты."""
        result = self.model.transcribe(
            audio_path,
            verbose=True,
            temperature=0,
            language="ru",
            condition_on_previous_text=False  # Критично важно!
        )
        time.sleep(1)
        return result["segments"]

    @staticmethod
    def format_time(seconds: float) -> str:
        """Форматирует время в читаемый формат (HH:MM:SS)."""
        return str(timedelta(seconds=round(seconds)))

    @staticmethod
    def merge_adjacent_utterances(utterances: List[Utterance], max_pause: float = 1.0) -> List[Utterance]:
        """
        Объединяет соседние реплики одного и того же говорящего,
        если пауза между ними меньше max_pause секунд.
        """
        if not utterances:
            return []

        merged = [utterances[0]]

        for current in utterances[1:]:
            last = merged[-1]

            # Если тот же говорящий и пауза небольшая - объединяем
            if (current.speaker == last.speaker and
                    current.start_time - last.end_time <= max_pause):
                new_text = f"{last.text} {current.text}"
                new_utterance = Utterance(
                    speaker=last.speaker,
                    text=new_text,
                    start_time=last.start_time,
                    end_time=current.end_time
                )
                merged[-1] = new_utterance
            else:
                merged.append(current)

        return merged

    @staticmethod
    def analyze_conversation(client_segments: list[dict], operator_segments: list[dict]) -> ConversationAnalysis:
        """Анализирует сегменты клиента и оператора, возвращая структурированные данные."""
        utterances: List[Utterance] = []

        # Создаем объекты Utterance для клиента
        for seg in client_segments:
            utterances.append(Utterance(
                speaker="client",
                text=seg['text'],
                start_time=seg['start'],
                end_time=seg['end']
            ))

        # Создаем объекты Utterance для оператора
        for seg in operator_segments:
            utterances.append(Utterance(
                speaker="operator",
                text=seg['text'],
                start_time=seg['start'],
                end_time=seg['end']
            ))

        # Сортируем все реплики по времени начала
        utterances.sort(key=lambda x: x.start_time)

        # Объединяем соседние реплики одного говорящего
        utterances = ConversationAnalyzer.merge_adjacent_utterances(utterances)

        # Вычисляем общую продолжительность
        duration = max(u.end_time for u in utterances) if utterances else 0

        return ConversationAnalysis(
            utterances=utterances,
            duration=duration
        )

    def print_conversation(self, analysis: ConversationAnalysis):
        """Выводит отформатированную историю разговора."""
        print("\nХод разговора:")
        print("=" * 60)
        for utterance in analysis.utterances:
            start = self.format_time(utterance.start_time)
            end = self.format_time(utterance.end_time)
            print(f"[{start} - {end}] {utterance.speaker}: {utterance.text}")
            print("-" * 60)

    def analyze(self, audio_source: Union[str, bytes]) -> ConversationAnalysis:
        """
        Основной метод анализа разговора.

        :param audio_source: Путь к аудиофайлу, URL или бинарные данные аудио
        :return: Результаты анализа разговора
        """
        # Получаем локальный путь к файлу (скачиваем если это URL)
        local_path = self._ensure_local_file(audio_source)

        # Разделяем стереофайл на два монофайла
        left_path, right_path = self.split_stereo_audio(local_path)

        print(audio_source)

        # Транскрибируем оба канала
        client_segments = self.transcribe_audio(left_path)
        operator_segments = self.transcribe_audio(right_path)

        # Анализируем разговор
        analysis = self.analyze_conversation(client_segments, operator_segments)

        return analysis