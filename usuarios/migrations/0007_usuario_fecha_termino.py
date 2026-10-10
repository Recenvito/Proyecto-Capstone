from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0006_historialcontrasena'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='fecha_termino',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Fecha de desactivación',
            ),
        ),
    ]
