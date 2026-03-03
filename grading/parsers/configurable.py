"""
Configurable parser that uses FileFormatConfig settings.
"""
from typing import Optional
from grading.parsers.base import BaseParser, ParsedData, ParsedStudent, ParseError


class ConfigurableParser(BaseParser):
    """
    Parser that uses admin-defined format configuration.
    Supports both fixed-width and delimited formats.
    """
    
    def __init__(self, format_config):
        """
        Initialize parser with format configuration.
        
        Args:
            format_config: FileFormatConfig model instance
        """
        self.config = format_config
    
    def can_parse(self, file_content: str) -> bool:
        """This parser can handle any file with proper config."""
        return True
    
    def parse(self, file_content: str) -> ParsedData:
        """
        Parse file content according to the format configuration.
        
        Args:
            file_content: Raw text content of the file
            
        Returns:
            ParsedData with keys, students, and errors
        """
        result = ParsedData()
        lines = file_content.splitlines()
        
        for row_num, line in enumerate(lines, start=1):
            # Skip empty lines
            if not line.strip():
                continue
            
            try:
                parsed = self._parse_line(line, row_num)
                if parsed:
                    if parsed.is_key:
                        result.keys.append(parsed)
                    else:
                        result.students.append(parsed)
            except Exception as e:
                result.errors.append(ParseError(
                    row_number=row_num,
                    raw_line=line,
                    message=str(e)
                ))
        
        # Determine question count from key
        if result.has_key:
            result.question_count = len(result.primary_key.answers.rstrip())
        
        return result
    
    def _parse_line(self, line: str, row_num: int) -> Optional[ParsedStudent]:
        """
        Parse a single line according to format configuration.
        
        Args:
            line: Raw line text
            row_num: Line number in file
            
        Returns:
            ParsedStudent or None if line is invalid
        """
        if self.config.format_type == 'FIXED_WIDTH':
            return self._parse_fixed_width(line, row_num)
        else:
            return self._parse_delimited(line, row_num)
    
    def _parse_fixed_width(self, line: str, row_num: int) -> Optional[ParsedStudent]:
        """Parse a fixed-width formatted line."""
        # Ensure line is long enough
        min_length = max(
            self.config.student_no_end,
            self.config.student_name_end,
            self.config.answers_start
        )
        
        if len(line) < min_length:
            raise ValueError(f"Satır çok kısa: {len(line)} karakter (en az {min_length} gerekli)")
        
        # Extract fields
        student_no = line[self.config.student_no_start:self.config.student_no_end].strip()
        student_name = line[self.config.student_name_start:self.config.student_name_end].strip()
        
        # Extract answers
        if self.config.answers_end:
            answers = line[self.config.answers_start:self.config.answers_end].rstrip()
        else:
            answers = line[self.config.answers_start:].rstrip()
        
        # Extract booklet if configured
        booklet = ''
        if self.config.has_booklet_field and self.config.booklet_start is not None:
            if self.config.booklet_end:
                booklet = line[self.config.booklet_start:self.config.booklet_end].strip()
            else:
                booklet = line[self.config.booklet_start:].strip()
        
        # Check if this is an answer key
        is_key = self._is_key_line(student_no, student_name)
        
        return ParsedStudent(
            student_no=student_no,
            student_name=student_name,
            answers=answers,
            booklet=booklet,
            row_number=row_num,
            is_key=is_key
        )
    
    def _parse_delimited(self, line: str, row_num: int) -> Optional[ParsedStudent]:
        """Parse a delimited line."""
        delimiter = self.config.get_delimiter()
        parts = line.split(delimiter)
        
        if len(parts) < 3:
            raise ValueError(f"Yetersiz alan sayısı: {len(parts)} (en az 3 gerekli)")
        
        # Assume: student_no, student_name, answers [, booklet]
        student_no = parts[0].strip()
        student_name = parts[1].strip()
        answers = parts[2].rstrip()
        booklet = parts[3].strip() if len(parts) > 3 and self.config.has_booklet_field else ''
        
        # Check if this is an answer key
        is_key = self._is_key_line(student_no, student_name)
        
        return ParsedStudent(
            student_no=student_no,
            student_name=student_name,
            answers=answers,
            booklet=booklet,
            row_number=row_num,
            is_key=is_key
        )
    
    def _is_key_line(self, student_no: str, student_name: str) -> bool:
        """
        Check if this line is an answer key based on configuration.
        
        Args:
            student_no: Parsed student number
            student_name: Parsed student name
            
        Returns:
            True if this is an answer key line
        """
        key_identifier = self.config.key_identifier.upper()
        
        if self.config.key_identifier_field == 'student_no':
            return student_no.upper() == key_identifier
        else:  # student_name
            return key_identifier in student_name.upper()
