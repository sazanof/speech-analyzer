# Copyright (C) 2025 Mikhail Sazanov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# database/task_cleanup.py
from sqlmodel import update,col

from classes.logger import Logger
from database.database import write_session
from entities.recording_entity import RecordingEntity
from entities.enums.recording_task_status import RecordingTaskStatus


class TaskCleanup:
    @staticmethod
    def reset_stuck_tasks():
        """Сбрасывает зависшие задачи при запуске приложения"""
        with write_session() as session:
            # Сбрасываем зависшие задачи распознавания
            session.exec(
                update(RecordingEntity)
                .where(col(RecordingEntity.recognize_status).in_([
                    RecordingTaskStatus.PENDING.value,
                    RecordingTaskStatus.FAILED.value
                ]))
                .values(recognize_status=RecordingTaskStatus.NEW.value)
            )

            # Сбрасываем зависшие задачи анализа
            session.exec(
                update(RecordingEntity)
                .where(col(RecordingEntity.analysis_status).in_([
                    RecordingTaskStatus.PENDING.value,
                    RecordingTaskStatus.FAILED.value
                ]))
                .values(analysis_status=RecordingTaskStatus.NEW.value)
            )

            session.commit()
            Logger.info("Stuck tasks reset to NEW status")