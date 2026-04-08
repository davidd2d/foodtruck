from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('onboarding', '0002_remove_onboardingimport_images_onboardingimage_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='onboardingimage',
            name='image_type',
            field=models.CharField(
                choices=[('menu', 'Menu'), ('logo', 'Logo'), ('other', 'Other')],
                default='menu',
                max_length=20
            ),
        ),
    ]
