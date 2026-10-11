from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from pacientes.models import DocumentoPaciente, Paciente


def crear_pdf_demo():
    contenido = b'BT /F1 18 Tf 72 720 Td (DOCUMENTO DE PRUEBA - SIN DATOS REALES) Tj ET'
    objetos = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        b'/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        b'<< /Length ' + str(len(contenido)).encode() + b' >>\nstream\n'
        + contenido + b'\nendstream',
    ]
    salida = bytearray(b'%PDF-1.4\n')
    posiciones = [0]
    for numero, objeto in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida.extend(f'{numero} 0 obj\n'.encode() + objeto + b'\nendobj\n')
    xref = len(salida)
    salida.extend(f'xref\n0 {len(posiciones)}\n'.encode())
    salida.extend(b'0000000000 65535 f \n')
    for posicion in posiciones[1:]:
        salida.extend(f'{posicion:010} 00000 n \n'.encode())
    salida.extend(
        f'trailer\n<< /Size {len(posiciones)} /Root 1 0 R >>\n'
        f'startxref\n{xref}\n%%EOF\n'.encode()
    )
    return bytes(salida)


class Command(BaseCommand):
    help = 'Crea un informe PDF ficticio para validar el portal con la ficha de prueba.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar-datos-de-prueba', action='store_true',
            help='Confirma que se usará exclusivamente la ficha ficticia de pruebas.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Este comando solo se permite en desarrollo (DEBUG=True).')
        if not options['confirmar_datos_de_prueba']:
            raise CommandError('Agrega --confirmar-datos-de-prueba para crear el documento ficticio.')

        paciente = Paciente.objects.filter(
            rut='22222222-2', nombres='Paciente', apellido_paterno='De Prueba',
            apellido_materno='Portal',
        ).first()
        if paciente is None:
            raise CommandError('No se encontró la ficha ficticia autorizada (RUT 22222222-2).')

        documento, creado = DocumentoPaciente.objects.get_or_create(
            paciente=paciente, titulo='Informe ficticio para probar el portal',
            defaults={
                'descripcion': 'PDF de demostración sin información clínica real.',
                'publicado': True,
            },
        )
        if creado:
            documento.archivo.save('informe-ficticio-prueba.pdf', ContentFile(crear_pdf_demo()), save=True)
        self.stdout.write(self.style.SUCCESS(
            'Informe ficticio creado y publicado.' if creado
            else 'El informe ficticio ya estaba creado; no se duplicó.'
        ))
