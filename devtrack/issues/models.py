from abc import ABC, abstractmethod
import datetime


class BaseEntity(ABC):
    @abstractmethod
    def validate(self):
        pass

    def to_dict(self):
        return {
            key: value
            for key, value in self.__dict__.items()
        }


class Reporter(BaseEntity):
    def __init__(self, id, name, email, team):
        self.id = id
        self.name = name
        self.email = email
        self.team = team

    def validate(self):
        if not self.name or not self.name.strip():
            raise ValueError('Name cannot be empty')
        if not self.email or '@' not in self.email:
            raise ValueError('Invalid email')
        if not self.team or not self.team.strip():
            raise ValueError('Team cannot be empty')


class Issue(BaseEntity):
    ALLOWED_STATUSES = {'open', 'in_progress', 'resolved', 'closed'}
    ALLOWED_PRIORITIES = {'low', 'medium', 'high', 'critical'}

    def __init__(self, id, title, description, status, priority, reporter_id, created_at=None):
        self.id = id
        self.title = title
        self.description = description
        self.status = status
        self.priority = priority
        self.reporter_id = reporter_id
        self.created_at = created_at or str(datetime.datetime.now())

    def validate(self):
        if not self.title or not self.title.strip():
            raise ValueError('Title cannot be empty')
        if self.status not in self.ALLOWED_STATUSES:
            raise ValueError(f'Invalid status. Must be one of {self.ALLOWED_STATUSES}')
        if self.priority not in self.ALLOWED_PRIORITIES:
            raise ValueError(f'Invalid priority. Must be one of {self.ALLOWED_PRIORITIES}')
        if not isinstance(self.reporter_id, int):
            try:
                self.reporter_id = int(self.reporter_id)
            except (TypeError, ValueError):
                raise ValueError('Invalid reporter_id')

    def describe(self):
        return f"{self.title} [{self.priority}]"


class CriticalIssue(Issue):
    def describe(self):
        return f"[URGENT] {self.title} — needs immediate attention"


class LowPriorityIssue(Issue):
    def describe(self):
        return f"{self.title} — low priority, handle when free"
