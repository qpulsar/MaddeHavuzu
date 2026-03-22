"""
Faz 17: StudentGroup → Course yeniden adlandırma ve Course sistemi.

- StudentGroup modeli Course olarak yeniden adlandırıldı
- Course'a code, description, pools M2M eklendi; eski 'course' CharField kaldırıldı
- CourseSpecTable yeni model
- ExamApplication.group → ExamApplication.course yeniden adlandırıldı
- TestForm.course FK ve TestForm.pools M2M eklendi
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('itempool', '0016_faz16_pool_simplify'),
    ]

    operations = [
        # 1. StudentGroup → Course
        migrations.RenameModel(
            old_name='StudentGroup',
            new_name='Course',
        ),

        # 2. Eski CharField 'course' kaldır (StudentGroup'un dersi string olarak tutuyordu)
        migrations.RemoveField(
            model_name='course',
            name='course',
        ),

        # 3. Ders kodu ekle
        migrations.AddField(
            model_name='course',
            name='code',
            field=models.CharField(blank=True, max_length=50, verbose_name='Ders Kodu'),
        ),

        # 4. Açıklama alanı (StudentGroup'ta zaten vardı ama blank/null farklıydı — güncelle)
        migrations.AlterField(
            model_name='course',
            name='description',
            field=models.TextField(blank=True, default='', verbose_name='Açıklama'),
            preserve_default=False,
        ),

        # 5. Bağlı havuzlar M2M
        migrations.AddField(
            model_name='course',
            name='pools',
            field=models.ManyToManyField(
                blank=True,
                related_name='courses',
                to='itempool.itempool',
                verbose_name='Bağlı Madde Havuzları',
            ),
        ),

        # 6. Meta güncellemesi
        migrations.AlterModelOptions(
            name='course',
            options={
                'ordering': ['-created_at'],
                'verbose_name': 'Ders',
                'verbose_name_plural': 'Dersler',
            },
        ),

        # 7. ExamApplication.group → course
        migrations.RenameField(
            model_name='examapplication',
            old_name='group',
            new_name='course',
        ),

        # 8. ExamApplication unique_together güncelle
        migrations.AlterUniqueTogether(
            name='examapplication',
            unique_together={('test_form', 'course')},
        ),

        # 9. CourseSpecTable yeni model
        migrations.CreateModel(
            name='CourseSpecTable',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Tablo Adı')),
                ('rows_json', models.JSONField(default=list, verbose_name='Tablo Verisi')),
                ('total_questions', models.PositiveIntegerField(default=0, verbose_name='Toplam Soru Sayısı')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('course', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='spec_tables',
                    to='itempool.course',
                    verbose_name='Ders',
                )),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Oluşturan',
                )),
            ],
            options={
                'verbose_name': 'Belirtke Tablosu',
                'verbose_name_plural': 'Belirtke Tabloları',
                'ordering': ['-created_at'],
            },
        ),

        # 10. TestForm.course FK (nullable)
        migrations.AddField(
            model_name='testform',
            name='course',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='test_forms',
                to='itempool.course',
                verbose_name='Ders',
            ),
        ),

        # 11. TestForm.pools M2M
        migrations.AddField(
            model_name='testform',
            name='pools',
            field=models.ManyToManyField(
                blank=True,
                related_name='test_forms',
                to='itempool.itempool',
                verbose_name='Madde Havuzları',
            ),
        ),
    ]
