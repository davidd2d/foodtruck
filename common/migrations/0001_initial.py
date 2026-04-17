from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(db_index=True, max_length=128)),
                ('model', models.CharField(db_index=True, max_length=128)),
                ('object_id', models.CharField(db_index=True, max_length=64)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['created_at'], name='common_audi_created_75f4b8_idx'),
                    models.Index(fields=['action', 'created_at'], name='common_audi_action_71fe78_idx'),
                    models.Index(fields=['model', 'object_id'], name='common_audi_model_1a1592_idx'),
                ],
            },
        ),
    ]
