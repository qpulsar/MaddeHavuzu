"""
Django management command to create a default file format configuration.
"""
from django.core.management.base import BaseCommand
from grading.models import FileFormatConfig


class Command(BaseCommand):
    help = 'Creates a default file format configuration for optical reader files'

    def handle(self, *args, **options):
        if FileFormatConfig.objects.exists():
            self.stdout.write(self.style.WARNING('File format already exists. Skipping.'))
            return

        format_config = FileFormatConfig.objects.create(
            name='Optik Okuyucu Varsayılan',
            description='Varsayılan optik okuyucu formatı (sabit genişlik)',
            format_type='FIXED_WIDTH',
            student_no_start=0,
            student_no_end=12,
            student_name_start=15,
            student_name_end=38,
            answers_start=38,
            key_identifier='CEVAP',
            key_identifier_field='student_name',
            valid_options='ABCDE',
            blank_markers='-* .',
            is_active=True,
            is_default=True,
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Created default file format: {format_config.name}')
        )
