from dataclasses import dataclass, field
from typing import List


@dataclass
class Transaction:
    id: str
    type: str
    date: str
    amount: int
    category: str
    memo: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class Budget:
    month: str
    amount: int


@dataclass
class Category:
    name: str