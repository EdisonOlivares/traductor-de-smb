# Traductor de archivos SimuProc

Aplicación de escritorio para leer archivos guardados por SimuProc (`.smp`) y
convertirlos a código SimuProc legible. La aplicación usa únicamente
la biblioteca estándar de Python, principalmente `tkinter`, por lo que no
requiere instalar paquetes externos.

## Características

- Interfaz gráfica sencilla.
- Selección de archivos mediante un botón.
- Arrastrar y soltar archivos sobre la ventana en Windows.
- Traducción de palabras de memoria a instrucciones SimuProc.
- Asociación de códigos de operación con la tabla CSV del proyecto.
- Soporte para `LDT "texto"` y `EAP "texto"`.
- Separación de los datos almacenados después de `HLT`.
- Botón para copiar el resultado al portapapeles.
- Casilla opcional para agregar explicaciones al final de cada instrucción.

## Archivos del proyecto

### `traductor_simuproc.py`

Es el programa principal. Contiene:

- El lector de archivos de texto.
- La clasificación de cada línea.
- La carga de la tabla de instrucciones.
- La conversión de códigos numéricos.
- La generación del programa traducido.
- La interfaz gráfica de Tkinter.
- El soporte de arrastrar y soltar en Windows.

### `tabla_opcodes_simuproc.csv`

Es la tabla de instrucciones utilizada por el traductor. Tiene únicamente las
columnas necesarias:

```csv
codigo,nombre,sintaxis,descripcion
```

- `codigo`: código de dos dígitos guardado en la memoria.
- `nombre`: nombre de la instrucción.
- `sintaxis`: sintaxis esperada.
- `descripcion`: explicación usada cuando se activa la opción de comentarios.

La tabla se puede ampliar o corregir sin modificar el código Python, siempre
que se conserven esas cuatro columnas.

### Archivos `.smp`

Es el único formato de entrada admitido. SimuProc guarda sus programas en
archivos `.smp`.

## Requisitos

- Windows.
- Python 3.10 o posterior recomendado.
- Tkinter, que normalmente viene incluido con Python para Windows.
- No se necesitan paquetes de `pip`.

## Ejecución

Abre PowerShell y entra en la carpeta del proyecto:

```powershell
cd "ruta\al\proyecto"
```

Ejecuta la aplicación:

```powershell
python .\traductor_simuproc.py
```

Si el comando `python` no está disponible, prueba:

```powershell
py .\traductor_simuproc.py
```

También se puede abrir el archivo `traductor_simuproc.py` haciendo doble clic,
si la instalación de Python está asociada a los archivos `.py`.

## Uso de la interfaz

1. Ejecuta `traductor_simuproc.py`.
2. Pulsa **Abrir archivo .SMP**, o arrastra un archivo a la ventana.
3. El resultado aparecerá en el cuadro de texto.
4. Revisa el programa traducido.
5. Pulsa **Copiar resultado** para llevarlo al portapapeles.
6. Pega el resultado en SimuProc.

La casilla **Agregar comentarios** permite cambiar entre dos formatos:

Sin comentarios:

```text
LDA 100
MUL 101
EAP
```

Con comentarios:

```text
LDA 100 ; Carga en AX el contenido de una dirección de memoria.
MUL 101 ; Multiplica AX por el contenido de una dirección de memoria.
EAP ; Imprime en pantalla el contenido del registro AX.
```

## Cómo se interpreta una palabra de memoria

Las instrucciones numéricas de cinco dígitos se dividen así:

```text
01100
```

- `01`: código de operación.
- `100`: dirección de memoria u operando.

Por ejemplo:

| Valor guardado | Código | Operando | Resultado |
|---|---:|---:|---|
| `01100` | `01` | `100` | `LDA 100` |
| `22101` | `22` | `101` | `MUL 101` |
| `02201` | `02` | `201` | `STA 201` |
| `99000` | `99` | `000` | `HLT` |

Las instrucciones que usan registros o puertos pueden aparecer en una forma
textual especial. Por ejemplo:

```text
811,AX
```

se traduce como:

```text
OUT 1,AX
```

## Texto de las instrucciones

El traductor combina automáticamente el texto que sigue a `MSG`, `LDT` o
`EAP`.

Entrada:

```text
LDT
"Ingrese un dato"

EAP
"Resultado:"
```

Salida:

```text
LDT "Ingrese un dato"
EAP "Resultado:"
```

El `DB` que puede aparecer en el código interno del traductor significa
**Define Byte**, una representación temporal para texto aislado. No se muestra
como una instrucción separada cuando el texto pertenece a `MSG`, `LDT` o
`EAP`.

## Direcciones y espacios de memoria

SimuProc utiliza direcciones hexadecimales de tres dígitos, desde `000` hasta
`FFF` (0 a 4095). Cada línea después de la cabecera representa una posición
real de memoria, incluso si está vacía. Por tanto, una línea vacía no se
elimina: representa un hueco.

Si existen instrucciones en `000`, `001` y `003`, la salida conserva el salto:

```text
LDA 100
MUL 101
#003
JMP 200
```

El marcador `#003` significa que la siguiente instrucción pertenece a la
posición hexadecimal `003`; la posición `002` está vacía.

Los operandos de tres caracteres también pueden ser hexadecimales. Por
ejemplo, `30A2F` representa `JMP A2F`.

## Datos almacenados en memoria

El traductor conserva la dirección real de los datos binarios que aparecen
después de `HLT`. Si hay un bloque consecutivo en `100`, `101` y `102`, lo
representa así:

Entrada conceptual:

```text
LDA 100
MUL 101
HLT

0000101101010001
0100010101101111
0000000000001010
```

Salida:

```text
LDA 100
MUL 101
HLT

#100
0000101101010001
#101
0100010101101111
#102
0000000000001010
```

Si hay un hueco entre datos, se agrega otro marcador hexadecimal:

```text
#100
dato 1
#103
dato 2
```

En este caso las posiciones `101` y `102` están vacías.

## Formato esperado del archivo `.smp`

El lector espera tres líneas iniciales de cabecera. En los archivos observados
aparecen así:

```text
SimuProc 1.4 - Vlaye
1ba
134
```

Estas líneas no son instrucciones ni ocupan posiciones de la memoria del
programa:

- `SimuProc 1.4 - Vlaye` identifica la versión/formato del archivo.
- `1ba` y `134` son metadatos guardados por SimuProc para ese archivo.

El formato público de esos dos metadatos no está documentado en el proyecto,
por lo que el traductor los conserva como cabecera y no intenta interpretarlos
como código. La memoria comienza después de la tercera línea, en la dirección
`000`.

Después aparecen las celdas de memoria:

```text
01100

22101

42000
"Mensaje"
```

El traductor mantiene la posición de cada línea. Las celdas vacías no se
imprimen como instrucciones, pero provocan un marcador `#HEX` cuando existe
un salto entre dos celdas con contenido.

## Instrucciones conocidas

La lista completa se encuentra en
[`tabla_opcodes_simuproc.csv`](./tabla_opcodes_simuproc.csv). Algunos ejemplos:

| Código | Instrucción | Función |
|---:|---|---|
| `01` | `LDA` | Carga en AX el contenido de una dirección de memoria. |
| `02` | `STA` | Guarda el contenido de AX en una dirección de memoria. |
| `22` | `MUL` | Multiplica AX por el contenido de una dirección de memoria. |
| `23` | `DIV` | Divide AX entre el contenido de una dirección de memoria. |
| `40` | `LDT` | Lee un dato del teclado. |
| `41` | `EAP` | Imprime en pantalla el contenido del registro AX. |
| `42` | `MSG` | Muestra el texto entre comillas. |
| `55` | `LDF` | Carga en los registros de punto flotante BX:AX el número IEEE 754 almacenado desde la dirección indicada. |
| `56` | `STF` | Guarda en memoria el número IEEE 754 contenido en BX:AX. |
| `62` | `MULF` | Multiplica BX:AX por el número IEEE 754 de una dirección de memoria. |
| `81` | `OUT` | Envía el valor de un registro a un puerto. |
| `99` | `HLT` | Detiene la ejecución del programa. |

## Limitaciones actuales

- Se esperan tres líneas de cabecera antes de la memoria. La primera identifica
  la versión/formato; los otros dos valores se conservan como metadatos porque
  su significado interno no está documentado.
- Los códigos no incluidos en el CSV no se pueden traducir; se conservan como
  palabras de memoria (`DW`).
- Los datos se detectan principalmente como palabras binarias posteriores a
  `HLT`.
- Las posiciones se limitan al rango de memoria de SimuProc: `000` a `FFF`.
- Las celdas vacías se preservan como saltos de memoria mediante marcadores
  `#HEX`.
- El arrastrar y soltar usa la API nativa de Windows. El botón de apertura es
  la alternativa recomendada si el arrastre no responde.
- La traducción no ejecuta ni simula el programa; solamente transforma su
  representación.

## Solución de problemas

### No se abre la ventana

Comprueba que Python esté instalado:

```powershell
python --version
```

Después intenta:

```powershell
py .\traductor_simuproc.py
```

### No encuentra la tabla de instrucciones

Comprueba que estos dos archivos estén en la misma carpeta:

```text
traductor_simuproc.py
tabla_opcodes_simuproc.csv
```

### No funciona arrastrar y soltar

Usa el botón **Abrir archivo .SMP**. El archivo debe tener extensión `.smp`.

### Aparece `DW` en el resultado

Significa que el valor no pudo asociarse con un opcode conocido. Revisa si el
código aparece en la columna `codigo` del CSV y agrega su definición solamente
si conoces su significado real.

## Verificación básica

Para comprobar que el archivo Python no tiene errores de sintaxis:

```powershell
python -m py_compile .\traductor_simuproc.py
```

Este comando no abre la interfaz; únicamente valida el código.
