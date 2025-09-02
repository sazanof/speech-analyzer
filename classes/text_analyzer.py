# services/text_analyzer.py
import logging
from typing import List, Dict, Optional, Tuple, Union
from pydantic import BaseModel, Field
import pymorphy3
from rapidfuzz import fuzz, process
import re
from functools import lru_cache
import time
from collections import defaultdict
from entities.dictionary_entity import DictionaryType
from models.conversation_model import ConversationAnalysis, ConversationHighlight, ConversationModel
from models.recognizer_models import Utterance

logger = logging.getLogger(__name__)


class MatchHighlight(BaseModel):
    phrase: str
    start_pos: int
    end_pos: int
    dictionary_name: str
    match_type: str


class AnalysisResult(BaseModel):
    matched_phrases: Dict[int, List[str]] = Field(default_factory=dict)
    rude_words: List[str] = Field(default_factory=list)
    greetings: List[str] = Field(default_factory=list)
    other_matches: Dict[str, List[str]] = Field(default_factory=dict)
    highlights: List[ConversationHighlight] = Field(default_factory=list)
    text_with_highlights: Optional[str] = None

    def model_dump(self, *args, **kwargs):
        return {
            'matched_phrases': self.matched_phrases,
            'rude_words': self.rude_words,
            'greetings': self.greetings,
            'other_matches': self.other_matches,
            'highlights': [highlight.model_dump() for highlight in self.highlights],
            'text_with_highlights': self.text_with_highlights
        }


class CachedMorphAnalyzer:
    """Кэшированный морфологический анализатор"""

    def __init__(self):
        self.morph = pymorphy3.MorphAnalyzer()
        self.parse_cache = {}
        self.normalize_cache = {}

    @lru_cache(maxsize=10000)
    def cached_parse(self, word: str):
        return self.morph.parse(word)[0]

    @lru_cache(maxsize=10000)
    def cached_normalize(self, word: str) -> str:
        try:
            parsed = self.cached_parse(word)
            return parsed.normal_form
        except:
            return word.lower()


class FastTextAnalyzer:
    """Оптимизированный анализатор текста"""

    def __init__(self):
        self.morph = CachedMorphAnalyzer()
        self.short_words = {
            "я", "мне", "меня", "ты", "тебе", "тебя", "он", "его", "ей", "она",
            "мы", "нам", "нас", "вы", "вам", "вас", "они", "им", "их",
            "в", "на", "за", "под", "над", "от", "до", "из", "к", "по", "со", "у",
            "и", "а", "но", "да", "или", "ли", "же", "бы", "вот", "всё", "все",
            "не", "ни", "как", "так", "то", "это", "что", "чтоб", "чтобы", "для"
        }

        # Предварительно скомпилированные regex patterns
        self.word_pattern = re.compile(r'\b\w+\b')
        self.phrase_patterns = {}

        # Кэширование
        self.normalize_cache = {}
        self.phrase_positions_cache = {}
        self.similarity_cache = {}

    def is_short_word(self, word: str) -> bool:
        return len(word) <= 3 or word.lower() in self.short_words

    @lru_cache(maxsize=10000)
    def normalize_text(self, text: str) -> str:
        """Кэшированная нормализация текста"""
        words = text.lower().split()
        normalized_words = []
        for word in words:
            normalized_words.append(self.morph.cached_normalize(word))
        return " ".join(normalized_words)

    def find_phrase_positions(self, phrase: str, text: str) -> List[Tuple[int, int]]:
        """Быстрый поиск позиций фразы с кэшированием patterns"""
        cache_key = f"{phrase}_{text}"
        if cache_key in self.phrase_positions_cache:
            return self.phrase_positions_cache[cache_key]

        if phrase not in self.phrase_patterns:
            self.phrase_patterns[phrase] = re.compile(r'\b' + re.escape(phrase) + r'\b', re.IGNORECASE)

        pattern = self.phrase_patterns[phrase]
        positions = [(match.start(), match.end()) for match in pattern.finditer(text)]

        self.phrase_positions_cache[cache_key] = positions
        return positions

    def is_phrase_in_text(self, phrase: str, text: str, threshold: float = 0.8) -> Tuple[
        bool, str, List[Tuple[int, int]]]:
        """
        Оптимизированная проверка вхождения фразы
        """
        # 1. Быстрая проверка точного совпадения
        if phrase.lower() in text.lower():
            exact_positions = self.find_phrase_positions(phrase, text)
            if exact_positions:
                return True, "exact", exact_positions

        # 2. Быстрая проверка частичного совпадения
        norm_phrase = self.normalize_text(phrase)
        norm_text = self.normalize_text(text)

        # 3. Для коротких фраз - быстрая проверка
        if len(phrase.split()) <= 3:
            if all(word in norm_text.split() for word in norm_phrase.split()):
                fuzzy_positions = self.find_fuzzy_positions(phrase, text)
                return True, "partial", fuzzy_positions

        # 4. Быстрый fuzzy matching
        similarity = fuzz.partial_ratio(norm_phrase, norm_text) / 100
        if similarity >= threshold:
            fuzzy_positions = self.find_fuzzy_positions(phrase, text)
            if fuzzy_positions:
                return True, "fuzzy", fuzzy_positions

        return False, "none", []

    def find_fuzzy_positions(self, phrase: str, text: str) -> List[Tuple[int, int]]:
        """Быстрый поиск fuzzy позиций"""
        words = phrase.split()
        positions = []
        text_lower = text.lower()

        for word in words:
            if not self.is_short_word(word):
                # Быстрый поиск слова в тексте
                match = re.search(r'\b' + re.escape(word) + r'\b', text_lower)
                if match:
                    positions.append((match.start(), match.end()))
                else:
                    # Быстрый fuzzy search для похожих слов
                    text_words = self.word_pattern.findall(text_lower)
                    if text_words:
                        best_match, score, _ = process.extractOne(word, text_words, scorer=fuzz.ratio)
                        if score >= 80:  # Высокий порог для fuzzy
                            match = re.search(r'\b' + re.escape(best_match) + r'\b', text_lower)
                            if match:
                                positions.append((match.start(), match.end()))

        return positions

    def add_highlights_to_text(self, text: str, highlights: List[ConversationHighlight]) -> str:
        """Оптимизированное добавление подсветок"""
        if not highlights:
            return text

        # Убираем дубликаты и сортируем
        unique_highlights = {}
        for highlight in highlights:
            key = (highlight.start_pos, highlight.end_pos)
            if key not in unique_highlights:
                unique_highlights[key] = highlight

        sorted_highlights = sorted(unique_highlights.values(), key=lambda x: x.start_pos)

        # Быстрое построение результата
        result_parts = []
        last_pos = 0

        for highlight in sorted_highlights:
            if highlight.start_pos > last_pos:
                result_parts.append(text[last_pos:highlight.start_pos])

            highlighted_text = text[highlight.start_pos:highlight.end_pos]
            result_parts.append(
                f'<mark style="background-color:{highlight.dictionary_color or "#cccccc"}" class="match {highlight.match_type}" data-dict-name="{highlight.dictionary_name}" data-dict="{highlight.dictionary_id}">{highlighted_text}</mark>'
            )
            last_pos = highlight.end_pos

        if last_pos < len(text):
            result_parts.append(text[last_pos:])

        return ''.join(result_parts)


class TextAnalyzer:
    """Основной класс анализатора с оптимизациями"""

    def __init__(self):
        self.fast_analyzer = FastTextAnalyzer()
        self.rude_words = ["дурак", "идиот", "кретин", "мудак", "сволочь"]
        self.greetings = ["здравствуйте", "добрый день", "доброе утро", "добрый вечер", "приветствую"]

        # Предварительная обработка словарей
        self.preprocessed_rude = set(self.rude_words)
        self.preprocessed_greetings = set(self.greetings)

        # Кэш анализа
        self.analysis_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0

    def analyze_utterance(self, utterance: Utterance, dictionaries: List[Dict]) -> AnalysisResult:
        """Оптимизированный анализ высказывания"""
        cache_key = f"{utterance.text}_{hash(str(dictionaries))}"

        # Проверка кэша
        if cache_key in self.analysis_cache:
            self.cache_hits += 1
            return self.analysis_cache[cache_key]

        self.cache_misses += 1
        result = AnalysisResult()

        # Быстрая проверка грубостей и приветствий
        text_lower = utterance.text.lower()
        result.rude_words = [w for w in self.rude_words if w in text_lower]
        result.greetings = [g for g in self.greetings if g in text_lower]

        # Параллельная обработка словарей
        for dictionary in dictionaries:
            dict_type = dictionary["type"]
            if ((dict_type == DictionaryType.CLIENT and utterance.speaker != "client")
                    or (dict_type == DictionaryType.OPERATOR and utterance.speaker != "operator")):
                continue

            matched = []
            for phrase in dictionary["phrases"]:
                found, match_type, positions = self.fast_analyzer.is_phrase_in_text(phrase, utterance.text)

                if found:
                    matched.append(phrase)
                    for start_pos, end_pos in positions:
                        result.highlights.append(
                            ConversationHighlight(
                                phrase=phrase,
                                start_pos=start_pos,
                                end_pos=end_pos,
                                dictionary_name=dictionary["name"],
                                dictionary_id=dictionary["id"],
                                dictionary_color=dictionary["color"],
                                match_type=match_type
                            )
                        )

            if matched:
                result.matched_phrases[dictionary["id"]] = matched

        # Создаем текст с подсветками
        if result.highlights:
            result.text_with_highlights = self.fast_analyzer.add_highlights_to_text(
                utterance.text, result.highlights
            )
        else:
            result.text_with_highlights = utterance.text

        # Сохраняем в кэш
        self.analysis_cache[cache_key] = result
        if len(self.analysis_cache) > 1000:  # Ограничиваем размер кэша
            self.analysis_cache.clear()

        return result

    def analyze_conversation_batch(self, conversation: List[Dict | Utterance], dictionaries: List[Dict]) -> Dict[
        str, AnalysisResult]:
        """Пакетный анализ разговора"""
        results = {}

        for utterance_dict in conversation:
            utterance = Utterance(**utterance_dict) if isinstance(utterance_dict, dict) else utterance_dict
            results[f"{utterance.speaker}_{utterance.start_time}"] = self.analyze_utterance(utterance, dictionaries)

        logger.info(
            f"Cache stats: hits={self.cache_hits}, misses={self.cache_misses}, ratio={self.cache_hits / (self.cache_hits + self.cache_misses) if self.cache_hits + self.cache_misses > 0 else 0:.2f}")

        return results

    def get_conversation_with_highlights(self, conversation: List[Dict | Utterance], dictionaries: List[Dict],
                                         recording_id: int) -> List[ConversationModel]:
        """Быстрое получение разговора с подсветками"""
        analyzed = self.analyze_conversation_batch(conversation, dictionaries)
        result = []

        for utterance_dict in conversation:
            utterance = Utterance(**utterance_dict) if isinstance(utterance_dict, dict) else utterance_dict
            key = f"{utterance.speaker}_{utterance.start_time}"
            analysis = analyzed[key]

            result.append(ConversationModel(
                recording_id=recording_id,
                speaker=utterance.speaker,
                text=utterance.text,
                text_with_highlights=analysis.text_with_highlights,
                start_time=utterance.start_time,
                end_time=utterance.end_time,
                analysis=ConversationAnalysis(
                    matched_phrases=analysis.matched_phrases,
                    highlights=analysis.highlights,
                )
            ))

        return result

    def preprocess_dictionaries(self, dictionaries: List[Dict]) -> None:
        """Предварительная обработка словарей для ускорения"""
        for dictionary in dictionaries:
            dictionary['phrases_set'] = set(dictionary['phrases'])
            dictionary['phrases_lower'] = [phrase.lower() for phrase in dictionary['phrases']]

    def clear_cache(self):
        """Очистка кэша"""
        self.analysis_cache.clear()
        self.fast_analyzer.normalize_text.cache_clear()
        self.fast_analyzer.morph.cached_parse.cache_clear()
        self.fast_analyzer.morph.cached_normalize.cache_clear()