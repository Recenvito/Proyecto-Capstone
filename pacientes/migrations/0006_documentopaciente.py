import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import pacientes.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pacientes', '0005_tutor_usuario_solicitudaccesotutor'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentoPaciente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=150)),
                ('descripcion', models.CharField(blank=True, max_length=300)),
                ('archivo', models.FileField(
                    upload_to=pacientes.models.ruta_informe_paciente,
                    validators=[
                        django.core.validators.FileExtensionValidator(['pdf']),
                        pacientes.models.validar_archivo_pdf,
                    ],
                )),
                ('fecha_documento', models.DateField(default=django.utils.timezone.localdate)),
                ('publicado', models.BooleanField(default=False)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('paciente', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='documentos_portal', to='pacientes.paciente',
                )),
                ('subido_por', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='documentos_pacientes_subidos', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Informe para portal de pacientes',
                'verbose_name_plural': 'Informes para portal de pacientes',
                'ordering': ['-fecha_documento', '-creado_en'],
            },
        ),
    ]
