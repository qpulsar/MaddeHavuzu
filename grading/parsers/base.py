"""
Base parser interface and data classes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ParsedStudent:
    """Represents a parsed student record."""
    student_no: str
    student_name: str
    answers: str
    booklet: str = ''
    row_number: int = 0
    is_key: bool = False


@dataclass
class ParseError:
    """Represents a parsing error."""
    row_number: int
    raw_line: str
    message: str


@dataclass
class ParsedData:
    """Result of parsing a file."""
    keys: List[ParsedStudent] = field(default_factory=list)
    students: List[ParsedStudent] = field(default_factory=list)
    errors: List[ParseError] = field(default_factory=list)
    question_count: int = 0
    
    @property
    def has_key(self) -> bool:
        return len(self.keys) > 0
    
    @property
    def has_multiple_keys(self) -> bool:
        return len(self.keys) > 1
    
    @property
    def primary_key(self) -> Optional[ParsedStudent]:
        """Get the primary (first) answer key."""
        return self.keys[0] if self.keys else None


class BaseParser(ABC):
    """
    Abstract base class for file parsers.
    Implement this interface to create custom parsers for different file formats.
    """
    
    @abstractmethod
    def parse(self, file_content: str) -> ParsedData:
        """
        Parse file content and return structured data.
        
        Args:
            file_content: Raw text content of the file
            
        Returns:
            ParsedData object containing keys, students, and errors
        """
        pass
    
    @abstractmethod
    def can_parse(self, file_content: str) -> bool:
        """
        Check if this parser can handle the given file content.
        
        Args:
            file_content: Raw text content of the file
            
        Returns:
            True if this parser can handle the file
        """
        pass
