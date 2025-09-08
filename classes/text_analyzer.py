# services/text_analyzer.py
import logging
from typing import List, Dict, Optional, Tuple, Set
from pydantic import BaseModel, Field
import pymorphy3
from rapidfuzz import fuzz
import re
from functools import lru_cache
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


class EnhancedMorphAnalyzer:
    """Улучшенный морфологический анализатор с кэшированием"""

    def __init__(self):
        self.morph = pymorphy3.MorphAnalyzer()
        self.normalize_cache = {}
        self.phrase_normalize_cache = {}

    @lru_cache(maxsize=10000)
    def normalize_word(self, word: str) -> str:
        """Нормализация одного слова"""
        try:
            parsed = self.morph.parse(word)[0]
            return parsed.normal_form
        except:
            return word.lower()

    def normalize_phrase(self, phrase: str) -> str:
        """Нормализация целой фразы с кэшированием"""
        if phrase in self.phrase_normalize_cache:
            return self.phrase_normalize_cache[phrase]

        words = re.findall(r'\b\w+\b', phrase.lower())
        normalized_words = [self.normalize_word(word) for word in words]
        result = ' '.join(normalized_words)

        self.phrase_normalize_cache[phrase] = result
        return result

    def get_phrase_keywords(self, phrase: str) -> Set[str]:
        """Извлечение ключевых слов из фразы (исключая стоп-слова)"""
        stop_words = {
            "я", "мне", "меня", "ты", "тебе", "тебя", "он", "его", "ей", "она",
            "мы", "нам", "нас", "вы", "вам", "вас", "они", "им", "их",
            "в", "на", "за", "под", "над", "от", "до", "из", "к", "по", "со", "у",
            "и", "а", "но", "да", "или", "ли", "же", "бы", "вот", "всё", "все",
            "не", "ни", "как", "так", "то", "это", "что", "чтоб", "чтобы", "для",
            "о", "об", "про", "с", "со", "из-за", "из", "от", "до", "по", "под",
            "над", "перед", "при", "через", "сквозь", "между", "среди", "вокруг"
        }

        words = re.findall(r'\b\w+\b', phrase.lower())
        keywords = {self.normalize_word(word) for word in words
                    if len(word) > 2 and word not in stop_words}
        return keywords


class EnhancedTextAnalyzer:
    """Улучшенный анализатор текста с учетом морфологии целых фраз"""

    def __init__(self):
        self.morph = EnhancedMorphAnalyzer()

        # Предварительно скомпилированные regex patterns
        self.word_pattern = re.compile(r'\b\w+\b')
        self.phrase_patterns = {}

    def find_exact_phrase_positions(self, phrase: str, text: str) -> List[Tuple[int, int]]:
        """Точный поиск позиций фразы"""
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        return [(match.start(), match.end()) for match in pattern.finditer(text)]

    def find_normalized_phrase_positions(self, phrase: str, text: str) -> List[Tuple[int, int]]:
        """Поиск позиций нормализованной фразы"""
        norm_phrase = self.morph.normalize_phrase(phrase)
        norm_text = self.morph.normalize_phrase(text)

        # Ищем нормализованную фразу в нормализованном тексте
        pattern = re.compile(re.escape(norm_phrase), re.IGNORECASE)
        matches = list(pattern.finditer(norm_text))

        if not matches:
            return []

        # Преобразуем позиции из нормализованного текста в оригинальный
        original_positions = []
        text_words = list(self.word_pattern.finditer(text))
        norm_text_words = list(self.word_pattern.finditer(norm_text))

        for match in matches:
            # Находим соответствующие слова в оригинальном тексте
            start_idx = len(norm_text[:match.start()].split())
            end_idx = len(norm_text[:match.end()].split())

            if start_idx < len(text_words) and end_idx <= len(text_words):
                start_pos = text_words[start_idx].start()
                end_pos = text_words[end_idx - 1].end() if end_idx > 0 else text_words[-1].end()
                original_positions.append((start_pos, end_pos))

        return original_positions

    def is_phrase_in_text(self, phrase: str, text: str, threshold: float = 0.85) -> Tuple[
        bool, str, List[Tuple[int, int]]]:
        """
        Улучшенная проверка вхождения фразы с учетом морфологии
        """
        # 1. Точное совпадение
        exact_positions = self.find_exact_phrase_positions(phrase, text)
        if exact_positions:
            return True, "exact", exact_positions

        # 2. Нормализованное совпадение (учитывает морфологию)
        normalized_positions = self.find_normalized_phrase_positions(phrase, text)
        if normalized_positions:
            return True, "normalized", normalized_positions

        # 3. Семантическое сходство для длинных фраз
        if len(phrase.split()) >= 3:
            norm_phrase = self.morph.normalize_phrase(phrase)
            norm_text = self.morph.normalize_phrase(text)

            # Проверяем ключевые слова
            phrase_keywords = self.morph.get_phrase_keywords(phrase)
            text_keywords = self.morph.get_phrase_keywords(text)

            # Должно быть не менее 70% ключевых слов
            if phrase_keywords and text_keywords:
                common_keywords = phrase_keywords & text_keywords
                keyword_similarity = len(common_keywords) / len(phrase_keywords)

                if keyword_similarity >= 0.7:
                    # Дополнительная проверка fuzzy similarity
                    similarity = fuzz.partial_ratio(norm_phrase, norm_text) / 100
                    if similarity >= threshold:
                        # Находим позиции ключевых слов
                        positions = []
                        for keyword in common_keywords:
                            # Ищем ключевые слова в тексте
                            for match in re.finditer(r'\b' + re.escape(keyword) + r'\b', norm_text, re.IGNORECASE):
                                # Находим соответствующую позицию в оригинальном тексте
                                original_match = list(self.word_pattern.finditer(text))[match.start()]
                                positions.append((original_match.start(), original_match.end()))

                        if positions:
                            return True, "semantic", positions

        return False, "none", []

    def add_highlights_to_text(self, text: str, highlights: List[ConversationHighlight]) -> str:
        """Добавление подсветок с обработкой пересечений"""
        if not highlights:
            return text

        # Убираем дубликаты и сортируем
        unique_highlights = {}
        for highlight in highlights:
            key = (highlight.start_pos, highlight.end_pos)
            if key not in unique_highlights:
                unique_highlights[key] = highlight

        sorted_highlights = sorted(unique_highlights.values(), key=lambda x: x.start_pos)

        # Обрабатываем пересекающиеся подсветки
        merged_highlights = []
        current_highlight = None

        for highlight in sorted_highlights:
            if current_highlight is None:
                current_highlight = highlight
            elif highlight.start_pos <= current_highlight.end_pos:
                # Объединяем пересекающиеся подсветки
                current_highlight = ConversationHighlight(
                    phrase=f"{current_highlight.phrase}|{highlight.phrase}",
                    start_pos=min(current_highlight.start_pos, highlight.start_pos),
                    end_pos=max(current_highlight.end_pos, highlight.end_pos),
                    dictionary_name="multiple",
                    dictionary_id=0,
                    dictionary_color="#ff9900",
                    match_type="merged"
                )
            else:
                merged_highlights.append(current_highlight)
                current_highlight = highlight

        if current_highlight:
            merged_highlights.append(current_highlight)

        # Быстрое построение результата
        result_parts = []
        last_pos = 0

        for highlight in merged_highlights:
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
    """Основной класс анализатора с улучшенной морфологией"""

    def __init__(self):
        self.enhanced_analyzer = EnhancedTextAnalyzer()
        self.preprocessed_dictionaries = {}

        # Кэш анализа
        self.analysis_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0

    def preprocess_dictionaries(self, dictionaries: List[Dict]) -> None:
        """Предварительная обработка словарей"""
        self.preprocessed_dictionaries = {}
        for dictionary in dictionaries:
            dict_id = dictionary["id"]
            self.preprocessed_dictionaries[dict_id] = {
                'original': dictionary,
                'normalized_phrases': [self.enhanced_analyzer.morph.normalize_phrase(phrase)
                                       for phrase in dictionary["phrases"]],
                'phrase_keywords': [self.enhanced_analyzer.morph.get_phrase_keywords(phrase)
                                    for phrase in dictionary["phrases"]]
            }

    def analyze_utterance(self, utterance: Utterance, dictionaries: List[Dict]) -> AnalysisResult:
        """Улучшенный анализ высказывания с учетом морфологии"""
        cache_key = f"{utterance.text}_{hash(str(dictionaries))}"

        if cache_key in self.analysis_cache:
            self.cache_hits += 1
            return self.analysis_cache[cache_key]

        self.cache_misses += 1
        result = AnalysisResult()

        # Предварительная обработка словарей, если не сделана
        if not self.preprocessed_dictionaries:
            self.preprocess_dictionaries(dictionaries)

        # Анализ для каждого словаря
        for dictionary in dictionaries:
            dict_type = dictionary["type"]
            if ((dict_type == DictionaryType.CLIENT and utterance.speaker != "client")
                    or (dict_type == DictionaryType.OPERATOR and utterance.speaker != "operator")):
                continue

            matched = []
            for phrase in dictionary["phrases"]:
                found, match_type, positions = self.enhanced_analyzer.is_phrase_in_text(phrase, utterance.text)

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
            result.text_with_highlights = self.enhanced_analyzer.add_highlights_to_text(
                utterance.text, result.highlights
            )
        else:
            result.text_with_highlights = utterance.text

        # Сохраняем в кэш
        self.analysis_cache[cache_key] = result
        if len(self.analysis_cache) > 1000:
            self.analysis_cache.clear()

        return result

    # Остальные методы остаются без изменений
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

    def clear_cache(self):
        """Очистка кэша"""
        self.analysis_cache.clear()
        self.enhanced_analyzer.morph.normalize_word.cache_clear()