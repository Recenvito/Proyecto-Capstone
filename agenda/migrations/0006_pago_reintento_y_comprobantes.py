from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0005_pagocita_asignacion_vinculo_creado'),
    ]

    operations = [
        migrations.AddField(
            model_name='pagocita',
            name='reintento_presencial',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='pagocita',
            name='comprobante_reserva_enviado_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pagocita',
            name='comprobante_pago_enviado_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
