# Migration to add users field to TenantGroup model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('documents', '1099_merge_20260122_0811'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenantgroup',
            name='users',
            field=models.ManyToManyField(
                blank=True,
                help_text='Users in this tenant group',
                related_name='tenant_groups',
                to='auth.user',
                verbose_name='users',
            ),
        ),
    ]
