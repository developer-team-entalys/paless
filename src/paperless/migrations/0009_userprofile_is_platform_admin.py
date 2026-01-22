# Generated migration for adding is_platform_admin field to UserProfile

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('paperless', '0008_assign_users_to_acme_tenant'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='is_platform_admin',
            field=models.BooleanField(
                default=False,
                help_text='Platform administrators can manage all tenants',
                verbose_name='is platform admin'
            ),
        ),
    ]
