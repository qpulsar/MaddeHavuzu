from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grading', '0007_faz13_uploadsession_test_form_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='theme',
            field=models.CharField(
                choices=[('light', 'Aydınlık'), ('dark', 'Karanlık'), ('system', 'Sistem (OS)')],
                default='light',
                max_length=10,
                verbose_name='Tema Modu',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='color_palette',
            field=models.CharField(
                choices=[
                    ('ocean',    'Okyanus'),
                    ('forest',   'Orman'),
                    ('sunset',   'Gün Batımı'),
                    ('amethyst', 'Ametist'),
                    ('midnight', 'Gece Mavisi'),
                    ('rose',     'Pembe'),
                ],
                default='ocean',
                max_length=20,
                verbose_name='Renk Paleti',
            ),
        ),
    ]
