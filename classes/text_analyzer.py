# services/text_analyzer.py
import logging
from typing import List, Dict, Optional, Tuple, Union
from pydantic import BaseModel, Field
import pymorphy3
from rapidfuzz import fuzz
import re
from entities.dictionary_entity import DictionaryType
from models.conversation_model import ConversationAnalysis, ConversationHighlight, ConversationModel
from models.recognizer_models import Utterance

logger = logging.getLogger(__name__)


class MatchHighlight(BaseModel):
    phrase: str
    start_pos: int
    end_pos: int
    dictionary_name: str
    match_type: str  # "exact", "partial", "fuzzy"


class AnalysisResult(BaseModel):
    """Pydantic модель для результатов анализа с правильной сериализацией"""
    matched_phrases: Dict[int, List[str]] = Field(default_factory=dict)
    rude_words: List[str] = Field(default_factory=list)
    greetings: List[str] = Field(default_factory=list)
    other_matches: Dict[str, List[str]] = Field(default_factory=dict)
    highlights: List[ConversationHighlight] = Field(default_factory=list)
    text_with_highlights: Optional[str] = None

    # Переопределяем метод для корректной сериализации
    def model_dump(self, *args, **kwargs):
        # Явно преобразуем все поля в сериализуемые типы
        return {
            'matched_phrases': self.matched_phrases,
            'rude_words': self.rude_words,
            'greetings': self.greetings,
            'other_matches': self.other_matches,
            'highlights': [highlight.model_dump() for highlight in self.highlights],
            'text_with_highlights': self.text_with_highlights
        }


class TextAnalyzer:
    def __init__(self):
        self.morph = pymorphy3.MorphAnalyzer()
        self.rude_words = ["дурак", "идиот", "кретин", "мудак", "сволочь"]
        self.greetings = ["здравствуйте", "добрый день", "доброе утро", "добрый вечер", "приветствую"]

    def normalize_text(self, text: str) -> str:
        words = text.lower().split()
        normalized_words = []
        for word in words:
            try:
                parsed = self.morph.parse(word)[0]
                normalized_words.append(parsed.normal_form)
            except:
                normalized_words.append(word)
        return " ".join(normalized_words)

    def find_phrase_positions(self, phrase: str, text: str) -> List[Tuple[int, int]]:
        """Находит позиции фразы в тексте с учетом регистра"""
        positions = []
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)

        for match in pattern.finditer(text):
            positions.append((match.start(), match.end()))

        return positions

    def is_phrase_in_text(self, phrase: str, text: str, threshold: float = 0.8) -> Tuple[
        bool, str, List[Tuple[int, int]]]:
        """
        Улучшенная проверка вхождения фразы в текст
        Возвращает (найдено_ли, тип_совпадения, позиции)
        """
        # 1. Проверка точного вхождения
        exact_positions = self.find_phrase_positions(phrase, text)
        if exact_positions:
            return True, "exact", exact_positions

        # 2. Нормализация для fuzzy matching
        norm_phrase = self.normalize_text(phrase)
        norm_text = self.normalize_text(text)

        # 3. Проверка вхождения всех слов
        text_words = norm_text.split()
        phrase_words = norm_phrase.split()

        if all(word in text_words for word in phrase_words):
            # Ищем приблизительные позиции
            fuzzy_positions = self.find_fuzzy_positions(phrase, text)
            return True, "partial", fuzzy_positions

        # 4. Fuzzy matching для частичного совпадения
        if len(phrase_words) > 1:
            similarity = fuzz.partial_ratio(norm_phrase, norm_text) / 100
            if similarity >= threshold:
                fuzzy_positions = self.find_fuzzy_positions(phrase, text)
                return True, "fuzzy", fuzzy_positions
        else:
            # Для отдельных слов
            for word in text_words:
                if fuzz.ratio(norm_phrase, word) / 100 >= threshold:
                    fuzzy_positions = self.find_fuzzy_positions(phrase, text)
                    return True, "fuzzy", fuzzy_positions

        return False, "none", []

    def find_fuzzy_positions(self, phrase: str, text: str) -> List[Tuple[int, int]]:
        """Находит приблизительные позиции для fuzzy совпадений"""
        words = phrase.split()
        positions = []

        for word in words:
            word_positions = self.find_phrase_positions(word, text)
            positions.extend(word_positions)

        return positions

    def add_highlights_to_text(self, text: str, highlights: List[ConversationHighlight]) -> str:
        """Добавляет HTML разметку для подсветки совпадений"""
        if not highlights:
            return text

        # Сортируем подсветки по позиции
        highlights.sort(key=lambda x: x.start_pos)

        # Создаем текст с разметкой
        result = []
        last_pos = 0

        for highlight in highlights:
            # Текст до подсветки
            if highlight.start_pos > last_pos:
                result.append(text[last_pos:highlight.start_pos])

            # Подсвеченный текст
            highlighted_text = text[highlight.start_pos:highlight.end_pos]
            result.append(
                f'<mark class="match {highlight.match_type}" data-dict="{highlight.dictionary_name}">{highlighted_text}</mark>')

            last_pos = highlight.end_pos

        # Текст после последней подсветки
        if last_pos < len(text):
            result.append(text[last_pos:])

        return ''.join(result)

    def analyze_utterance(
            self,
            utterance: Utterance,  # Теперь принимает объект Utterance
            dictionaries: List[Dict]
    ) -> AnalysisResult:
        result = AnalysisResult()

        # Проверка на грубости и приветствия
        result.rude_words = [w for w in self.rude_words if self.is_phrase_in_text(w, utterance.text)[0]]
        result.greetings = [g for g in self.greetings if self.is_phrase_in_text(g, utterance.text)[0]]

        # Проверка по кастомным словарям
        for dictionary in dictionaries:
            dict_type = dictionary["type"]
            if ((dict_type == DictionaryType.CLIENT and utterance.speaker != "client")
                    or (dict_type == DictionaryType.OPERATOR and utterance.speaker != "operator")):
                continue

            matched = []
            for phrase in dictionary["phrases"]:
                found, match_type, positions = self.is_phrase_in_text(phrase, utterance.text)

                if found:
                    matched.append(phrase)

                    # Добавляем подсветки для каждого совпадения
                    for start_pos, end_pos in positions:
                        result.highlights.append(
                            ConversationHighlight(
                                phrase=phrase,
                                start_pos=start_pos,
                                end_pos=end_pos,
                                dictionary_name=dictionary["name"],
                                dictionary_id=dictionary["id"],
                                match_type=match_type
                            )
                        )

            if matched:
                result.matched_phrases[dictionary["id"]] = matched

        # Создаем текст с подсветками
        if result.highlights:
            result.text_with_highlights = self.add_highlights_to_text(
                utterance.text,
                result.highlights
            )
        else:
            result.text_with_highlights = utterance.text

        return result

    def analyze_conversation(
            self,
            conversation: List[Dict | Utterance],  # Принимаем список словарей
            dictionaries: List[Dict]
    ) -> Dict[str, AnalysisResult]:
        results = {}
        for utterance_dict in conversation:
            # Преобразуем словарь в объект Utterance
            if type(utterance_dict) == dict:
                utterance = Utterance(**utterance_dict)
            else:
                utterance = utterance_dict
            results[f"{utterance.speaker}_{utterance.start_time}"] = self.analyze_utterance(utterance, dictionaries)
        return results

    def get_conversation_with_highlights(
            self,
            conversation: List[Dict | Utterance],  # Принимаем список словарей
            dictionaries: List[Dict],
            recording_id: int
    ) -> List[ConversationModel]:
        """Возвращает разговор с подсветками для фронтенда"""
        analyzed = self.analyze_conversation(conversation, dictionaries)

        result = []
        for utterance_dict in conversation:
            if isinstance(utterance_dict, dict):
                utterance = Utterance(**utterance_dict)
            else:
                utterance = utterance_dict
            key = f"{utterance.speaker}_{utterance.start_time}"
            analysis = analyzed[key]

            analys = ConversationAnalysis(
                matched_phrases=analysis.matched_phrases,
                highlights=analysis.highlights,
            )

            conversation = ConversationModel(
                recording_id=recording_id,
                speaker=utterance.speaker,
                text=utterance.text,
                text_with_highlights=analysis.text_with_highlights,
                start_time=utterance.start_time,
                end_time=utterance.end_time,
                analysis=analys
            )

            result.append(conversation)
        return result
